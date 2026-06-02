#!/usr/bin/env python3
"""
uart_node.py
============
Bridges ROS2 topics ↔ STM32 over UART.

Topics
------
Subscriptions:
  /arm/cmd   (arm_interfaces/ArmCmd)   — receive commands from any ROS2 node or web

Publishers:
  /arm/status (arm_interfaces/ArmStatus) — joint positions + moving flags
  /arm/raw_rx (std_msgs/String)          — raw STM32 output (debugging)

Parameters
----------
  port      : UART port  (default /dev/ttyAMA0)
  baudrate  : baud rate  (default 115200)
  default_speed : steps/sec  (default 600.0)
  default_accel : steps/sec² (default 2000.0)
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

from arm_interfaces.msg import ArmCmd, ArmStatus
from std_msgs.msg import String

import serial
import threading
import queue
import time


QOS = QoSProfile(
    reliability=ReliabilityPolicy.RELIABLE,
    history=HistoryPolicy.KEEP_LAST,
    depth=10,
)


class UartNode(Node):

    def __init__(self):
        super().__init__('uart_node')

        # ---- Parameters ----
        self.declare_parameter('port',          '/dev/ttyAMA0')
        self.declare_parameter('baudrate',      115200)
        self.declare_parameter('default_speed', 600.0)
        self.declare_parameter('default_accel', 2000.0)

        self._port    = self.get_parameter('port').value
        self._baud    = self.get_parameter('baudrate').value
        self._def_spd = self.get_parameter('default_speed').value
        self._def_acc = self.get_parameter('default_accel').value

        # ---- State ----
        self._positions = [0.0] * 6
        self._moving    = [False] * 6
        self._tx_queue  = queue.Queue()

        # ---- UART ----
        try:
            self._ser = serial.Serial(self._port, self._baud, timeout=1)
            time.sleep(1.0)
            self._ser.reset_input_buffer()
            self._ser.reset_output_buffer()
            self.get_logger().info(f'UART opened: {self._port} @ {self._baud}')
        except serial.SerialException as e:
            self.get_logger().error(f'UART open failed: {e}')
            raise

        # ---- Publishers ----
        self._pub_status = self.create_publisher(ArmStatus, '/arm/status', QOS)
        self._pub_raw    = self.create_publisher(String,     '/arm/raw_rx', QOS)

        # ---- Subscriber ----
        self._sub_cmd = self.create_subscription(
            ArmCmd, '/arm/cmd', self._on_cmd, QOS)

        # ---- Status poll timer (every 200 ms) ----
        self.create_timer(0.2, self._request_status)

        # ---- UART threads ----
        threading.Thread(target=self._rx_loop, daemon=True).start()
        threading.Thread(target=self._tx_loop, daemon=True).start()

        self.get_logger().info('UART Node ready ✔')

    # ==============================================================
    #  COMMAND HANDLER
    # ==============================================================
    def _on_cmd(self, msg: ArmCmd):
        cmd  = msg.command.strip().upper()
        mid  = int(msg.motor_id)
        ang  = float(msg.angle)
        spd  = float(msg.speed)  if msg.speed  > 0 else self._def_spd
        acc  = float(msg.accel)  if msg.accel  > 0 else self._def_acc

        if cmd == 'MOVE':
            if not 1 <= mid <= 6:
                self.get_logger().warn(f'MOVE: invalid motor_id {mid}')
                return
            self._moving[mid - 1] = True
            self._send(f'M:{mid}:{ang:.2f}:{spd:.0f}:{acc:.0f}')

        elif cmd == 'STOP':
            for i in range(6):
                self._moving[i] = False
            self._send('STOP')

        elif cmd == 'ZERO':
            if not 1 <= mid <= 6:
                self.get_logger().warn(f'ZERO: invalid motor_id {mid}')
                return
            self._send(f'Z:{mid}')

        elif cmd == 'ENABLE':
            self._send('ENABLE:1')

        elif cmd == 'DISABLE':
            self._send('ENABLE:0')

        elif cmd == 'STATUS':
            self._send('STATUS')

        else:
            self.get_logger().warn(f'Unknown command: {cmd}')

    # ==============================================================
    #  TX
    # ==============================================================
    def _send(self, cmd: str):
        self._tx_queue.put(cmd)

    def _tx_loop(self):
        while True:
            try:
                cmd   = self._tx_queue.get(timeout=1)
                frame = f'<{cmd}>'
                self._ser.write(frame.encode())
                self._ser.flush()
                self.get_logger().debug(f'[TX] → {frame}')
            except queue.Empty:
                continue
            except Exception as e:
                self.get_logger().error(f'TX error: {e}')

    # ==============================================================
    #  RX
    # ==============================================================
    def _rx_loop(self):
        while True:
            try:
                raw   = self._ser.readline()
                line  = raw.decode(errors='ignore').strip()
                if not line:
                    continue

                # Publish raw for debugging / web monitor
                raw_msg      = String()
                raw_msg.data = line
                self._pub_raw.publish(raw_msg)

                if line.startswith('POS:'):
                    self._parse_pos(line)

                elif line.startswith('OK:DONE:'):
                    self._parse_done(line)

                elif line.startswith(('OK:', 'ERR:', 'READY')):
                    self.get_logger().info(f'[STM32] {line}')

            except Exception as e:
                self.get_logger().error(f'RX error: {e}')

    # ==============================================================
    #  PARSE STM32 RESPONSES
    # ==============================================================
    def _parse_pos(self, line: str):
        """POS:a1:a2:a3:a4:a5:a6"""
        try:
            parts = line[4:].split(':')
            for i, p in enumerate(parts[:6]):
                self._positions[i] = float(p)
            self._publish_status(line)
        except Exception as e:
            self.get_logger().error(f'POS parse error: {e} | line={line}')

    def _parse_done(self, line: str):
        """OK:DONE:id"""
        try:
            mid = int(line.split(':')[2]) - 1   # 0-based
            if 0 <= mid < 6:
                self._moving[mid] = False
                self.get_logger().info(f'Motor {mid+1} reached target ✓')
            self._publish_status(line)
        except Exception as e:
            self.get_logger().error(f'DONE parse error: {e}')

    def _publish_status(self, raw: str):
        msg              = ArmStatus()
        msg.stamp        = self.get_clock().now().to_msg()
        msg.positions    = list(self._positions)
        msg.moving       = list(self._moving)
        msg.raw_response = raw
        self._pub_status.publish(msg)

    # ==============================================================
    #  PERIODIC STATUS REQUEST
    # ==============================================================
    def _request_status(self):
        self._send('STATUS')


# ==============================================================
def main(args=None):
    rclpy.init(args=args)
    node = UartNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

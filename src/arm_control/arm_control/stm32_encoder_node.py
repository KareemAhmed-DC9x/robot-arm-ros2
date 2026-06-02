#!/usr/bin/env python3
"""
stm32_encoder_node.py
=====================
ROS2 Jazzy node — publishes encoder counts and limit switch states
from the STM32 firmware to the ROS2 ecosystem.

تم تعديله لدعم:
- كشف فوري لـ LS6 (limit switch 6) عبر تحليل الخطوط الخام.
- إرسال STOP مباشرة إلى STM32 motors (via /dev/ttyAMA0) بأقصى سرعة.
- إرسال ZERO عبر ROS2 بعد التوقف.
"""

import sys
import os
import threading
import time
import re
import serial
from arm_interfaces.srv import GripperCmd
sys.path.insert(0, os.path.dirname(__file__))
from stm32_encoder import STM32Bridge, LimitState, EncoderLevel, NUM_CHANNELS, NUM_LIMITS

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup

from std_msgs.msg import Float64MultiArray, Int32MultiArray, String, Int32
from arm_interfaces.msg import ArmCmd

# ── QoS (لم نغيره) ──
QOS_RT = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT, history=HistoryPolicy.KEEP_LAST, depth=5)
QOS_REL = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, history=HistoryPolicy.KEEP_LAST, depth=10)


class STM32EncoderNode(Node):

    def __init__(self):
        super().__init__('stm32_encoder_node')

        # ── Parameters (baudrate لم يتغير) ──
        self.declare_parameter('port', '/dev/ttyAMA2')
        self.declare_parameter('baudrate', 115200)   # يبقى 115200
        self.declare_parameter('poll_rate_hz', 10.0)
        self.declare_parameter('verbose', False)

        port = self.get_parameter('port').value
        baud = self.get_parameter('baudrate').value
        hz = self.get_parameter('poll_rate_hz').value
        verbose = self.get_parameter('verbose').value

        # ── STM32 bridge (لقراءة الحساسات) ──
        try:
            self._bridge = STM32Bridge(
                port=port, baudrate=baud, verbose=verbose,
                on_heartbeat=self._on_heartbeat
            )
        except RuntimeError as e:
            self.get_logger().fatal(f'STM32 bridge failed: {e}')
            raise

        self.get_logger().info(f'STM32EncoderNode: {port} @ {baud} poll={hz}Hz')

        # ── Publishers ──
        self._pub_counts = self.create_publisher(Float64MultiArray, '/arm/encoder/counts', QOS_REL)
        self._pub_levels = self.create_publisher(Int32MultiArray, '/arm/encoder/levels', QOS_REL)
        self._pub_limits = self.create_publisher(Int32MultiArray, '/arm/limit/states', QOS_REL)
        self._pub_raw = self.create_publisher(String, '/arm/stm32/raw', QOS_REL)
        self._pub_gripper_state = self.create_publisher(String, '/arm/gripper/state', QOS_REL)
        self._pub_gripper_count = self.create_publisher(Int32, '/arm/gripper/count', QOS_REL)
        self._pub_arm_cmd = self.create_publisher(ArmCmd, '/arm/cmd', QOS_REL)  # لإرسال ZERO

        # ── Subscribers ──
        self._sub_reset = self.create_subscription(Int32, '/arm/encoder/reset', self._on_reset, QOS_REL)

        # ── Gripper service ──
        self._gripper_srv = self.create_service(
            GripperCmd, '/arm/gripper/cmd', self._handle_gripper_cmd,
            callback_group=MutuallyExclusiveCallbackGroup()
        )

        # ── Poll timer ──
        self._poll_timer = self.create_timer(1.0 / hz, self._poll)

        # ── Internal state ──
        self._counts = [0] * NUM_CHANNELS
        self._levels = [0] * NUM_CHANNELS
        self._limits = [0] * NUM_LIMITS
        self._lock = threading.Lock()
        self._gripper_state_str = "UNKNOWN"
        self._gripper_count = 0

        # ── Fast detection of LS6 ──
        self._ls6_was_active = False

        # (اختياري) اشتراك احتياطي عبر polling (لن يستخدم للسرعة)
        self.create_subscription(Int32MultiArray, '/arm/limit/states', self._auto_zero_on_ls6_backup, QOS_REL)

    # ═══════════════════════════════════════════════════════════
    #  HEARTBEAT – أسرع نقطة لاستقبال البيانات من STM32
    # ═══════════════════════════════════════════════════════════
    def _on_heartbeat(self, line: str):
        # نشر الخط الخام (للتشخيص)
        raw_msg = String()
        raw_msg.data = line
        self._pub_raw.publish(raw_msg)

        # معالجة بيانات الـ gripper (كما هي)
        if "[GRIPPER]" in line:
            self._parse_gripper_response(line)

        # ⭐ FAST DETECTION: البحث عن تفعيل LIMIT_6 (LS6)
        # تنسيق الخط المتوقع: "LIMIT_6: ACTIVE" أو "LIMIT_6: NOT_ACTIVE"
        match = re.match(r'LIMIT_(\d+):\s*(ACTIVE|NOT_ACTIVE)', line)
        if match:
            limit_id = int(match.group(1))
            state = match.group(2)
            is_active = (state == "ACTIVE")
            if limit_id == 6:   # LS6 الخاص بالمحرك M4
                if is_active and not self._ls6_was_active:
                    self.get_logger().info("[FAST HOME] LS6 activated → DIRECT STOP + ZERO for M4")
                    # 1) إيقاف فوري عبر المنفذ التسلسلي للمحركات (يتجاوز ROS2)
                    self._send_stop_direct_to_motor_stm32(4)
                    # 2) إرسال ZERO عبر ROS2 (أو يمكن إرساله مباشرة أيضاً)
                    self._send_zero_via_ros2(4)
                self._ls6_was_active = is_active

    # ── إرسال STOP مباشرة إلى STM32 الخاص بالمحركات (أقصى سرعة) ──
    def _send_stop_direct_to_motor_stm32(self, motor_id: int):
        """إرسال أمر STOP مباشرة إلى /dev/ttyAMA0 – يتجاوز ROS2 بالكامل"""
        try:
            # فتح المنفذ وإرسال الأمر (لا نستخدم lock طويل)
            with serial.Serial('/dev/ttyAMA0', 115200, timeout=0.01) as ser:
                # صيغة الأمر حسب بروتوكول STM32 motor. غيّرها إذا لزم الأمر.
                # مثال: "STOP\n" (إذا كان الأمر عاماً لجميع المحركات)
                cmd = "STOP\n"
                ser.write(cmd.encode())
                ser.flush()
                self.get_logger().info(f"[DIRECT STOP] STOP sent to motor {motor_id} via /dev/ttyAMA0")
        except Exception as e:
            self.get_logger().error(f"Direct STOP failed: {e}")

    # ── إرسال أمر ZERO عبر ROS2 (يمكن إرساله مباشرة أيضاً) ──
    def _send_zero_via_ros2(self, motor_id: int):
        zero_cmd = ArmCmd()
        zero_cmd.command = "ZERO"
        zero_cmd.motor_id = motor_id
        zero_cmd.angle = 0.0
        zero_cmd.speed = 0.0
        zero_cmd.accel = 0.0
        self._pub_arm_cmd.publish(zero_cmd)
        self.get_logger().info(f"[ZERO] ZERO command sent to M{motor_id} via ROS2")

    # ═══════════════════════════════════════════════════════════
    #  باقي الدوال (Gripper, Reset, Poll, backup subscription)
    # ═══════════════════════════════════════════════════════════
    def _parse_gripper_response(self, line: str):
        self.get_logger().debug(f"Parsing gripper response: {line}")
        if "STATE:" in line:
            if "OPENING" in line:
                self._gripper_state_str = "OPENING"
            elif "CLOSING" in line:
                self._gripper_state_str = "CLOSING"
            elif "OPEN" in line and "CLOSING" not in line:
                self._gripper_state_str = "OPEN"
            elif "CLOSED" in line:
                self._gripper_state_str = "CLOSED"
            if "count=" in line:
                try:
                    cnt_str = line.split("count=")[1].split()[0]
                    self._gripper_count = int(cnt_str)
                except:
                    pass
        elif "target reached" in line:
            if "OPEN" in line:
                self._gripper_state_str = "OPEN"
            elif "CLOSED" in line:
                self._gripper_state_str = "CLOSED"
            if "count=" in line:
                try:
                    cnt_str = line.split("count=")[1].split()[0]
                    self._gripper_count = int(cnt_str)
                except:
                    pass
        elif "COUNT:" in line:
            try:
                cnt_str = line.split("COUNT:")[1].strip()
                self._gripper_count = int(cnt_str)
            except:
                pass
        elif "Stopped" in line:
            self._gripper_state_str = "STOPPED"
        self._publish_gripper_state()

    def _publish_gripper_state(self):
        state_msg = String()
        state_msg.data = self._gripper_state_str
        self._pub_gripper_state.publish(state_msg)
        cnt_msg = Int32()
        cnt_msg.data = self._gripper_count
        self._pub_gripper_count.publish(cnt_msg)

    async def _handle_gripper_cmd(self, request, response):
        cmd = request.command.lower().strip()
        self.get_logger().info(f"Gripper command received: {cmd}")
        if cmd == "open":
            ok = self._bridge.gripper_command("OPEN")
            response.success = ok
            response.message = "Gripper opening" if ok else "Failed to send OPEN"
            if ok:
                self._gripper_state_str = "OPEN"
                self._publish_gripper_state()
        elif cmd == "close":
            ok = self._bridge.gripper_command("CLOSE")
            response.success = ok
            response.message = "Gripper closing" if ok else "Failed to send CLOSE"
            if ok:
                self._gripper_state_str = "CLOSED"
                self._publish_gripper_state()
        elif cmd == "stop":
            ok = self._bridge.gripper_command("STOP")
            response.success = ok
            response.message = "Gripper stop command sent" if ok else "Failed to send STOP"
            if ok:
                self._gripper_state_str = "STOPPED"
                self._publish_gripper_state()
        elif cmd == "reset_count":
            ok = self._bridge.gripper_command("RESET")
            response.success = ok
            response.message = "Gripper count reset" if ok else "Failed to send RESET"
            if ok:
                self._gripper_count = 0
                self._publish_gripper_state()
        elif cmd == "get_state":
            ok = self._bridge.gripper_command("STATE")
            response.success = ok
            response.message = "State requested – check /arm/gripper/state"
        elif cmd == "get_count":
            ok = self._bridge.gripper_command("COUNT")
            response.success = ok
            response.message = "Count requested – check /arm/gripper/count"
        else:
            response.success = False
            response.message = f"Unknown command '{cmd}'"
        return response

    def _on_reset(self, msg: Int32):
        ch = msg.data
        if ch == 0:
            ok = self._bridge.reset_all()
            self.get_logger().info(f'Reset ALL encoders → {"ok" if ok else "fail"}')
        elif 1 <= ch <= NUM_CHANNELS:
            ok = self._bridge.reset_count(ch)
            self.get_logger().info(f'Reset encoder {ch} → {"ok" if ok else "fail"}')
        else:
            self.get_logger().warn(f'Reset: invalid channel {ch}')

    # ── نسخة احتياطية عبر polling (لن تؤثر على السرعة) ──
    def _auto_zero_on_ls6_backup(self, msg: Int32MultiArray):
        if len(msg.data) < 8:
            return
        ls6_active = (msg.data[5] == 1)
        if ls6_active and not self._ls6_was_active:
            self.get_logger().info("[BACKUP] LS6 detected via poll – sending STOP+ZERO (just in case)")
            self._send_stop_direct_to_motor_stm32(4)
            self._send_zero_via_ros2(4)
        self._ls6_was_active = ls6_active

    def _poll(self):
        try:
            counts_dict = self._bridge.get_all_counts()
            limits_dict = self._bridge.get_all_limits()
            levels_dict = self._bridge.get_all_encoder_levels()
            counts = [float(counts_dict.get(i, 0)) for i in range(1, NUM_CHANNELS + 1)]
            limits = [1 if limits_dict.get(i) == LimitState.ACTIVE else 0 for i in range(1, NUM_LIMITS + 1)]
            levels = [1 if levels_dict.get(i) == EncoderLevel.LOW else 0 for i in range(1, NUM_CHANNELS + 1)]
            with self._lock:
                self._counts = counts
                self._limits = limits
                self._levels = levels
            cnt_msg = Float64MultiArray(); cnt_msg.data = counts; self._pub_counts.publish(cnt_msg)
            lim_msg = Int32MultiArray(); lim_msg.data = limits; self._pub_limits.publish(lim_msg)
            lvl_msg = Int32MultiArray(); lvl_msg.data = levels; self._pub_levels.publish(lvl_msg)
            if not hasattr(self, '_poll_counter'):
                self._poll_counter = 0
            self._poll_counter += 1
            if self._poll_counter % 5 == 0:
                self._bridge.gripper_command("STATE")
                self._bridge.gripper_command("COUNT")
        except Exception as e:
            self.get_logger().error(f'Poll error: {e}')

    def destroy_node(self):
        self._bridge.close()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = STM32EncoderNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f'Fatal: {e}')
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
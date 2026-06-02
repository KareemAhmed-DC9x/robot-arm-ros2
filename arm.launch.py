
"""
arm.launch.py
=============
Launches:
  1. uart_node        — UART ↔ ROS2 bridge
  2. web_server_node  — HTTP + Socket.IO server for web UI

Run with:
  ros2 launch arm_control arm.launch.py
  ros2 launch arm_control arm.launch.py port:=/dev/ttyAMA0 baudrate:=115200
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():

    # ---- Arguments ----
    port_arg = DeclareLaunchArgument(
        'port', default_value='/dev/ttyAMA0',
        description='UART serial port')

    baud_arg = DeclareLaunchArgument(
        'baudrate', default_value='115200',
        description='UART baud rate')

    spd_arg = DeclareLaunchArgument(
        'default_speed', default_value='600.0',
        description='Default motor speed (steps/sec)')

    acc_arg = DeclareLaunchArgument(
        'default_accel', default_value='2000.0',
        description='Default motor accel (steps/sec²)')

    http_arg = DeclareLaunchArgument(
        'http_port', default_value='8080',
        description='Web server HTTP port')

    # ---- Nodes ----
    uart_node = Node(
        package='arm_control',
        executable='uart_node',
        name='uart_node',
        output='screen',
        parameters=[{
            'port':          LaunchConfiguration('port'),
            'baudrate':      LaunchConfiguration('baudrate'),
            'default_speed': LaunchConfiguration('default_speed'),
            'default_accel': LaunchConfiguration('default_accel'),
        }],
    )

    web_node = Node(
        package='arm_control',
        executable='web_server_node',
        name='web_server_node',
        output='screen',
        parameters=[{
            'http_port': LaunchConfiguration('http_port'),
        }],
    )

    return LaunchDescription([
        port_arg,
        baud_arg,
        spd_arg,
        acc_arg,
        http_arg,
        LogInfo(msg='Starting ARM ROS2 System...'),
        uart_node,
        web_node,
    ])

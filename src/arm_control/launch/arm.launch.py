"""
arm.launch.py
=============
Launches:
  1. uart_node             — التحكم في المحركات (موتورات) @ 115200
  2. stm32_encoder_node    — قراءة المشفرات والمفاتيح @ 115200 (متوافق)
  3. web_server_node       — واجهة ويب
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

def generate_launch_description():

    # ---- Arguments ----
    motor_port_arg = DeclareLaunchArgument(
        'motor_port', default_value='/dev/ttyAMA0',
        description='UART port for motor STM32')

    sensor_port_arg = DeclareLaunchArgument(
        'sensor_port', default_value='/dev/ttyAMA2',
        description='UART port for encoder STM32')

    # سرعتان منفصلتان (كلاهما 115200)
    motor_baud_arg = DeclareLaunchArgument(
        'motor_baudrate', default_value='115200',
        description='UART baud rate for motor STM32')

    sensor_baud_arg = DeclareLaunchArgument(
        'sensor_baudrate', default_value='115200',   # ← تم التغيير إلى 115200
        description='UART baud rate for encoder STM32')

    poll_arg = DeclareLaunchArgument(
        'poll_rate_hz', default_value='10.0',
        description='Polling rate for encoders/limits')

    verbose_arg = DeclareLaunchArgument(
        'verbose', default_value='false',
        description='Print raw STM32 messages')

    http_arg = DeclareLaunchArgument(
        'http_port', default_value='8080',
        description='Web server HTTP port')

    # ---- Motor Node (UART) - 115200 ----
    uart_node = Node(
        package='arm_control',
        executable='uart_node',
        name='uart_node',
        output='screen',
        parameters=[{
            'port': LaunchConfiguration('motor_port'),
            'baudrate': LaunchConfiguration('motor_baudrate'),
        }],
    )

    # ---- Encoder Node (STM32) - 115200 ----
    stm32_node = Node(
        package='arm_control',
        executable='stm32_encoder_node',
        name='stm32_encoder_node',
        output='screen',
        parameters=[{
            'port': LaunchConfiguration('sensor_port'),
            'baudrate': LaunchConfiguration('sensor_baudrate'),
            'poll_rate_hz': LaunchConfiguration('poll_rate_hz'),
            'verbose': LaunchConfiguration('verbose'),
        }],
    )

    # ---- Web Server Node ----
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
        motor_port_arg,
        sensor_port_arg,
        motor_baud_arg,
        sensor_baud_arg,
        poll_arg,
        verbose_arg,
        http_arg,
        LogInfo(msg='Starting ARM ROS2 System: motor@115200, sensor@115200, web...'),
        uart_node,
        stm32_node,
        web_node,
    ])
cmake_minimum_required(VERSION 3.8)
project(arm_interfaces)

find_package(ament_cmake REQUIRED)
find_package(std_msgs REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(rosidl_default_generators REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/ArmCmd.msg"
  "msg/ArmStatus.msg"
  "srv/GripperCmd.srv" 
  DEPENDENCIES
    std_msgs
    builtin_interfaces
)

ament_package() 

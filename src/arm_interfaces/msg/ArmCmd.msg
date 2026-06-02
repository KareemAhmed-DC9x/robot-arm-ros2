# ArmCmd.msg
# Command sent to UART node → forwarded to STM32
#
# command values:
#   MOVE    → move motor_id to angle
#   STOP    → stop all motors
#   ZERO    → set zero on motor_id
#   ENABLE  → enable driver
#   DISABLE → disable driver
#   STATUS  → request position status

uint8    motor_id    # 1-6 (0 = all, used for STOP)
string   command     # MOVE | STOP | ZERO | ENABLE | DISABLE | STATUS
float32  angle       # degrees on the LINK (positive / negative)
float32  speed       # steps/sec  (0 = use default 600)
float32  accel       # steps/sec² (0 = use default 2000)


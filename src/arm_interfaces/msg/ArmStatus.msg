# ArmStatus.msg
# Published by UART node when STM32 responds with POS: or OK:DONE

builtin_interfaces/Time stamp

float32[] positions     # 6 joint angles in degrees (link frame)
bool[]    moving        # 6 flags — true while motor is in motion
string    raw_response  # raw string from STM32 (for debugging)


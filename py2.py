import serial
import time

PORT = '/dev/ttyAMA0'
BAUD = 115200

def debug(msg):
    print(f"[PI DEBUG] {time.strftime('%H:%M:%S')} - {msg}")

while True:
    try:
        ser = serial.Serial(PORT, BAUD, timeout=1)
        time.sleep(2)

        debug("Serial connected successfully")

        while True:
            if ser.in_waiting > 0:
                data = ser.readline().decode('utf-8', errors='ignore').strip()

                if data:
                    debug(f"RX from STM32 -> {data}")

                    # رد مع debug
                    response = "Hello STM32 from Pi"
                    ser.write((response + "\n").encode())

                    debug(f"TX to STM32 -> {response}")

            time.sleep(0.1)

    except Exception as e:
        debug(f"ERROR: {e}")
        debug("Retrying in 3 seconds...")
        time.sleep(3) 

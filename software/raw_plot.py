import time
import numpy as np
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import serial


SER_PORT = "COM3"   # change to /dev/ttyUSB0 or /dev/ttyACM0 on Linux/macOS
SER_BAUD = 115200


def read_serial_and_plot():
    ser = serial.Serial(SER_PORT, SER_BAUD, timeout=1)
    time.sleep(0.5)
    print(f"[OK] Serial connected: {SER_PORT} @ {SER_BAUD}")

    buffer = []
    plt.figure(figsize=(12, 6))
    plt.title("Raw EEG waveform")
    plt.xlabel("Sample index")
    plt.ylabel("Amplitude")

    while True:
        try:
            line = ser.readline()
            if not line:
                continue

            try:
                value = int(line.decode("utf-8").strip())
            except Exception:
                continue

            buffer.append(value)
            if len(buffer) > 250:
                buffer.pop(0)

            plt.cla()
            plt.plot(buffer, color="black")
            plt.title("Raw EEG waveform")
            plt.xlabel("Sample index")
            plt.ylabel("Amplitude")
            plt.grid(True)
            plt.pause(0.01)

        except KeyboardInterrupt:
            print("Stopped by user.")
            break

    ser.close()


if __name__ == "__main__":
    read_serial_and_plot()

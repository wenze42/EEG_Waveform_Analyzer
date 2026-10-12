import time
import numpy as np
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import serial
from scipy.signal import butter, lfilter


SER_PORT = "COM3"   # change to /dev/ttyUSB0 or /dev/ttyACM0 on Linux/macOS
SER_BAUD = 115200
FS = 250


def bandpass(data, low, high, fs=FS):
    nyq = 0.5 * fs
    low_norm = low / nyq
    high_norm = high / nyq
    b, a = butter(4, [low_norm, high_norm], btype='bandpass')
    return lfilter(b, a, data)


def read_and_plot_bands():
    ser = serial.Serial(SER_PORT, SER_BAUD, timeout=1)
    time.sleep(0.5)
    print(f"[OK] Serial connected: {SER_PORT} @ {SER_BAUD}")

    raw_buffer = []
    alpha_buffer = []
    beta_buffer = []
    gamma_buffer = []

    plt.figure(figsize=(12, 10))

    while True:
        try:
            line = ser.readline()
            if not line:
                continue

            try:
                value = int(line.decode("utf-8").strip())
            except Exception:
                continue

            raw_buffer.append(float(value))
            if len(raw_buffer) > 250:
                raw_buffer.pop(0)

            data = np.asarray(raw_buffer, dtype=np.float32)
            if len(data) >= 50:
                alpha = bandpass(data, 8, 12, FS)
                beta = bandpass(data, 12, 30, FS)
                gamma = bandpass(data, 30, 100, FS)

                alpha_buffer = alpha[-250:]
                beta_buffer = beta[-250:]
                gamma_buffer = gamma[-250:]

            plt.clf()

            plt.subplot(4, 1, 1)
            plt.plot(raw_buffer, color='black')
            plt.title('Raw EEG')
            plt.grid(True)

            plt.subplot(4, 1, 2)
            plt.plot(alpha_buffer, color='blue')
            plt.title('Alpha (8-12 Hz)')
            plt.grid(True)

            plt.subplot(4, 1, 3)
            plt.plot(beta_buffer, color='green')
            plt.title('Beta (12-30 Hz)')
            plt.grid(True)

            plt.subplot(4, 1, 4)
            plt.plot(gamma_buffer, color='red')
            plt.title('Gamma (30-100 Hz)')
            plt.grid(True)

            plt.tight_layout()
            plt.pause(0.01)

        except KeyboardInterrupt:
            print("Stopped by user.")
            break

    ser.close()


if __name__ == "__main__":
    read_and_plot_bands()

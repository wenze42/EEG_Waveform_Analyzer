import time
import numpy as np
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt

from serial_reader import SerialEEGReader
from signal_processor import SignalProcessor


class EEGApp:
    def __init__(self, port="COM3", baudrate=115200):
        self.reader = SerialEEGReader(port, baudrate)
        self.processor = SignalProcessor(fs=250)

        self.raw_buffer = []
        self.alpha_buffer = []
        self.beta_buffer = []
        self.gamma_buffer = []

    def connect(self):
        return self.reader.open()

    def disconnect(self):
        self.reader.close()

    def update(self):
        raw = self.reader.get_latest(250)
        if len(raw) < 10:
            return

        raw = np.asarray(raw, dtype=np.float32)
        alpha = self.processor.alpha(raw)
        beta = self.processor.beta(raw)
        gamma = self.processor.gamma(raw)

        self.raw_buffer = raw
        self.alpha_buffer = alpha
        self.beta_buffer = beta
        self.gamma_buffer = gamma

    def plot(self):
        plt.figure(figsize=(12, 8))

        plt.subplot(4, 1, 1)
        plt.plot(self.raw_buffer, label='raw', color='black')
        plt.title('Raw EEG')
        plt.grid(True)

        plt.subplot(4, 1, 2)
        plt.plot(self.alpha_buffer, color='blue', label='alpha')
        plt.title('Alpha 8-12Hz')
        plt.grid(True)

        plt.subplot(4, 1, 3)
        plt.plot(self.beta_buffer, color='green', label='beta')
        plt.title('Beta 12-30Hz')
        plt.grid(True)

        plt.subplot(4, 1, 4)
        plt.plot(self.gamma_buffer, color='red', label='gamma')
        plt.title('Gamma 30-100Hz')
        plt.grid(True)

        plt.tight_layout()
        plt.pause(0.01)
        plt.clf()


if __name__ == "__main__":
    app = EEGApp(port="COM3")
    if not app.connect():
        print("Failed to connect to serial port. Please check COM port.")
        raise SystemExit(1)

    print("EEG monitor started. Press Ctrl+C to stop.")
    try:
        while True:
            app.update()
            if len(app.raw_buffer) > 0:
                app.plot()
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("Stopped by user.")
    finally:
        app.disconnect()

import serial
import time


class SerialEEGReader:
    def __init__(self, port="COM3", baudrate=115200, timeout=1):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None

    def open(self):
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
            time.sleep(0.5)
            print(f"[OK] Serial connected: {self.port} @ {self.baudrate}")
            return True
        except Exception as e:
            print(f"[ERR] Cannot open serial port: {e}")
            return False

    def close(self):
        if self.ser is not None:
            self.ser.close()
            self.ser = None
            print("[INFO] Serial port closed")

    def read_samples(self, count=250):
        if self.ser is None:
            return []

        samples = []
        for _ in range(count):
            line = self.ser.readline()
            if not line:
                continue
            try:
                value = int(line.decode("utf-8").strip())
                samples.append(value)
            except Exception:
                pass
        return samples

    def get_latest(self, n=250):
        if self.ser is None:
            return []

        data = []
        for _ in range(n):
            line = self.ser.readline()
            if not line:
                continue
            try:
                data.append(int(line.decode("utf-8").strip()))
            except Exception:
                pass
        return data

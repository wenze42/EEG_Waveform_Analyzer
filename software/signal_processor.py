import numpy as np
from scipy.signal import butter, lfilter


class SignalProcessor:
    def __init__(self, fs=250):
        self.fs = fs

    def bandpass(self, data, low, high):
        if len(data) < 10:
            return np.zeros_like(data, dtype=np.float32)

        nyq = 0.5 * self.fs
        low_norm = low / nyq
        high_norm = high / nyq

        if low_norm <= 0 or high_norm >= 1:
            raise ValueError(f"Invalid band settings: low={low}, high={high}, fs={self.fs}")

        b, a = butter(4, [low_norm, high_norm], btype='bandpass')
        return lfilter(b, a, data).astype(np.float32)

    def alpha(self, data):
        return self.bandpass(data, 8, 12)

    def beta(self, data):
        return self.bandpass(data, 12, 30)

    def gamma(self, data):
        return self.bandpass(data, 30, 100)

    def fft(self, data):
        if len(data) == 0:
            return np.array([]), np.array([])

        window = np.hanning(len(data))
        signal = data * window
        spectrum = np.abs(np.fft.rfft(signal))
        freqs = np.fft.rfftfreq(len(data), 1.0 / self.fs)
        return freqs, spectrum.astype(np.float32)

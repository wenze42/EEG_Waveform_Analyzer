"""EEG signal processing utilities.

Provides band-pass / notch filtering, band decomposition and FFT helpers
used by the analysis application. Filter coefficients are cached per
cut-off pair so repeated calls on short windows stay cheap.
"""

from __future__ import annotations

import numpy as np
from scipy.signal import butter, lfilter, iirnotch

import config


class SignalProcessor:
    """Time-domain and spectral processing for a single EEG channel."""

    def __init__(self, fs: float = config.SAMPLING_RATE,
                 bands: dict | None = None,
                 notch_freq: float = config.NOTCH_FREQ,
                 notch_q: float = config.NOTCH_Q):
        self.fs = fs
        self.bands = bands if bands is not None else config.FREQUENCY_BANDS
        self.notch_freq = notch_freq
        self.notch_q = notch_q

        # Coefficient cache: (kind, low, high) -> (b, a)
        self._bp_cache: dict[tuple, tuple[np.ndarray, np.ndarray]] = {}
        self._notch_coef: tuple[np.ndarray, np.ndarray] | None = None

    # ------------------------------------------------------------------ #
    #  Filter design helpers                                             #
    # ------------------------------------------------------------------ #
    def _bandpass_coef(self, low: float, high: float, order: int = 4):
        key = ("bp", round(low, 4), round(high, 4))
        coef = self._bp_cache.get(key)
        if coef is None:
            nyq = 0.5 * self.fs
            low_n, high_n = low / nyq, high / nyq
            if low_n <= 0.0 or high_n >= 1.0 or low_n >= high_n:
                raise ValueError(
                    f"Invalid bandpass [{low}, {high}] for fs={self.fs}"
                )
            coef = butter(order, [low_n, high_n], btype="bandpass")
            self._bp_cache[key] = coef
        return coef

    def _notch_coef(self):
        if self._notch_coef is None and self.notch_freq > 0:
            self._notch_coef = iirnotch(
                self.notch_freq / (0.5 * self.fs), self.notch_q
            )
        return self._notch_coef

    # ------------------------------------------------------------------ #
    #  Public filters                                                    #
    # ------------------------------------------------------------------ #
    def bandpass(self, data: np.ndarray, low: float, high: float) -> np.ndarray:
        data = np.asarray(data, dtype=np.float32)
        if data.size < 10:
            return np.zeros_like(data, dtype=np.float32)
        b, a = self._bandpass_coef(low, high)
        return lfilter(b, a, data).astype(np.float32)

    def notch(self, data: np.ndarray) -> np.ndarray:
        coef = self._notch_coef()
        if coef is None:
            return np.asarray(data, dtype=np.float32)
        b, a = coef
        return lfilter(b, a, np.asarray(data, dtype=np.float32)).astype(np.float32)

    def prefilter(self, data: np.ndarray) -> np.ndarray:
        """Apply high-pass to clean DC offset (ADS1291 handles 50Hz notch)."""
        out = np.asarray(data, dtype=np.float32)
        # 0.5 Hz high-pass to remove residual baseline drift.
        nyq = 0.5 * self.fs
        b, a = butter(2, 0.5 / nyq, btype="high")
        return lfilter(b, a, out).astype(np.float32)

    # ------------------------------------------------------------------ #
    #  Band-specific shortcuts                                           #
    # ------------------------------------------------------------------ #
    def delta(self, data: np.ndarray) -> np.ndarray:
        return self.bandpass(data, *self.bands["delta"])

    def theta(self, data: np.ndarray) -> np.ndarray:
        return self.bandpass(data, *self.bands["theta"])

    def alpha(self, data: np.ndarray) -> np.ndarray:
        return self.bandpass(data, *self.bands["alpha"])

    def beta(self, data: np.ndarray) -> np.ndarray:
        return self.bandpass(data, *self.bands["beta"])

    def gamma(self, data: np.ndarray) -> np.ndarray:
        return self.bandpass(data, *self.bands["gamma"])

    def decompose_bands(self, data: np.ndarray) -> dict[str, np.ndarray]:
        """Return dict {band_name: filtered_signal} for every configured band."""
        data = np.asarray(data, dtype=np.float32)
        return {
            name: self.bandpass(data, low, high)
            for name, (low, high) in self.bands.items()
        }

    # ------------------------------------------------------------------ #
    #  Spectral analysis                                                 #
    # ------------------------------------------------------------------ #
    def fft(self, data: np.ndarray, window: str = "hann"):
        data = np.asarray(data, dtype=np.float32)
        if data.size == 0:
            return np.array([]), np.array([])
        win = {
            "hann": np.hanning,
            "hamming": np.hamming,
            "blackman": np.blackman,
            "rect": lambda n: np.ones(n),
        }[window](data.size)
        spectrum = np.abs(np.fft.rfft(data * win))
        freqs = np.fft.rfftfreq(data.size, 1.0 / self.fs)
        return freqs, spectrum.astype(np.float32)

    def power_spectral_density(self, data: np.ndarray,
                               window: str = "hann") -> tuple[np.ndarray, np.ndarray]:
        """One-sided PSD (mean-square amplitude) per frequency bin."""
        freqs, spectrum = self.fft(data, window=window)
        if spectrum.size == 0:
            return freqs, spectrum
        psd = (spectrum ** 2) / np.sum(
            {
                "hann": np.hanning,
                "hamming": np.hamming,
                "blackman": np.blackman,
                "rect": lambda n: np.ones(n),
            }[window](data.size) ** 2
        )
        # Convert to single-sided and account for rfft packing.
        psd = 2.0 * psd / data.size
        psd[0] *= 0.5
        if data.size % 2 == 0 and psd.size > 1:
            psd[-1] *= 0.5
        return freqs, psd.astype(np.float32)

"""Feature extraction for EEG windows.

Computes per-band power, total power, alpha/beta ratio and basic
statistical descriptors from a raw signal window. Designed to be fed
either a raw buffer or a pre-decomposed band dictionary from
SignalProcessor.decompose_bands().
"""

from __future__ import annotations

import numpy as np

import config


class FeatureExtractor:
    def __init__(self, fs: float = config.SAMPLING_RATE,
                 bands: dict | None = None):
        self.fs = fs
        self.bands = bands if bands is not None else config.FREQUENCY_BANDS

    # ------------------------------------------------------------------ #
    #  Power / spectral                                                  #
    # ------------------------------------------------------------------ #
    def band_powers(self, signal: np.ndarray,
                    window: str = "hann") -> dict[str, float]:
        """Absolute power (mean-square) inside each configured band."""
        signal = np.asarray(signal, dtype=np.float32)
        if signal.size < 16:
            return {name: 0.0 for name in self.bands}

        win = np.hanning(signal.size)
        spectrum = np.abs(np.fft.rfft(signal * win)) ** 2
        freqs = np.fft.rfftfreq(signal.size, 1.0 / self.fs)
        # Single-sided correction.
        spectrum[1:-1 if signal.size % 2 == 0 else 1:] *= 2.0

        out: dict[str, float] = {}
        df = freqs[1] - freqs[0] if freqs.size > 1 else 1.0
        for name, (low, high) in self.bands.items():
            mask = (freqs >= low) & (freqs <= high)
            out[name] = float(np.sum(spectrum[mask]) * df)
        return out

    def total_power(self, signal: np.ndarray) -> float:
        signal = np.asarray(signal, dtype=np.float32)
        if signal.size == 0:
            return 0.0
        return float(np.mean(signal ** 2))

    def peak_frequency(self, signal: np.ndarray) -> float:
        signal = np.asarray(signal, dtype=np.float32)
        if signal.size < 16:
            return 0.0
        spectrum = np.abs(np.fft.rfft(signal * np.hanning(signal.size)))
        freqs = np.fft.rfftfreq(signal.size, 1.0 / self.fs)
        return float(freqs[int(np.argmax(spectrum[1:])) + 1]) \
            if spectrum.size > 1 else 0.0

    # ------------------------------------------------------------------ #
    #  Statistics                                                        #
    # ------------------------------------------------------------------ #
    def statistics(self, signal: np.ndarray) -> dict[str, float]:
        signal = np.asarray(signal, dtype=np.float32)
        if signal.size == 0:
            return {"mean": 0.0, "std": 0.0, "rms": 0.0, "peak_to_peak": 0.0}
        return {
            "mean": float(np.mean(signal)),
            "std": float(np.std(signal)),
            "rms": float(np.sqrt(np.mean(signal ** 2))),
            "peak_to_peak": float(np.ptp(signal)),
        }

    # ------------------------------------------------------------------ #
    #  Aggregate                                                         #
    # ------------------------------------------------------------------ #
    def extract_all_features(self, raw: np.ndarray,
                             decomposed: dict[str, np.ndarray] | None = None
                             ) -> dict[str, float]:
        raw = np.asarray(raw, dtype=np.float32)
        features: dict[str, float] = {}

        features.update(self.statistics(raw))
        features["total_power"] = self.total_power(raw)
        features["peak_freq"] = self.peak_frequency(raw)

        band_powers = self.band_powers(raw)
        for name, power in band_powers.items():
            features[f"power_{name}"] = power

        # Relative band shares.
        total = sum(band_powers.values()) or 1.0
        for name, power in band_powers.items():
            features[f"ratio_{name}"] = power / total

        # Engagement index (alpha / (beta + theta)) - a common alertness proxy.
        alpha = band_powers.get("alpha", 0.0)
        beta = band_powers.get("beta", 0.0)
        theta = band_powers.get("theta", 0.0)
        features["engagement_index"] = alpha / (beta + theta + 1e-9)

        # Optionally also compute band power from pre-filtered signals for
        # cross-validation with the time-domain decomposition.
        if decomposed:
            for name, sig in decomposed.items():
                sig = np.asarray(sig, dtype=np.float32)
                if sig.size:
                    features[f"time_power_{name}"] = float(np.mean(sig ** 2))

        return features

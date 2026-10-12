"""EEG application entry point.

Connects to the firmware over serial, drains newly arrived samples on each
tick, decomposes them into frequency bands, renders a live waveform and
periodically logs extracted features. Sessions are persisted to HDF5 + CSV
on exit.
"""

from __future__ import annotations

import time

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import numpy as np

import config
from data_manager import EEGDataManager
from feature_extractor import FeatureExtractor
from logger import logger
from serial_reader import SerialEEGReader
from signal_processor import SignalProcessor

# Bands shown in the live plot (keep the view compact).
PLOT_BANDS = ["alpha", "beta", "gamma"]


class EEGAnalyzerApp:
    def __init__(self, port=config.SERIAL_PORT, baudrate=config.SERIAL_BAUD):
        self.serial = SerialEEGReader(port=port, baudrate=baudrate,
                                      timeout=config.SERIAL_TIMEOUT)
        self.processor = SignalProcessor(fs=config.SAMPLING_RATE)
        self.feature_extractor = FeatureExtractor(fs=config.SAMPLING_RATE)
        self.data_manager = EEGDataManager(data_dir=config.DATA_DIR)
        self.raw_buffer: list[float] = []
        self.band_buffers: dict[str, list[float]] = {
            name: [] for name in config.FREQUENCY_BANDS.keys()
        }
        self.running = False
        self._last_metrics_log = 0.0

    # ------------------------------------------------------------------ #
    def connect(self) -> bool:
        if not self.serial.open():
            return False
        self.running = True
        self.serial.start_reading()
        return True

    def disconnect(self):
        self.running = False
        self.serial.stop_reading()
        self.serial.close()

    # ------------------------------------------------------------------ #
    def update(self):
        if not self.running:
            return

        new_samples = self.serial.drain_new_samples()
        if new_samples.size == 0:
            return

        # Optionally clean the stream before analysis.
        cleaned = self.processor.prefilter(new_samples)
        self.raw_buffer.extend(cleaned.tolist())
        if len(self.raw_buffer) > config.BUFFER_SIZE:
            self.raw_buffer = self.raw_buffer[-config.BUFFER_SIZE:]

        signal = np.asarray(self.raw_buffer, dtype=np.float32)
        if signal.size > 50:
            decomposed = self.processor.decompose_bands(signal)
            for band_name, band_signal in decomposed.items():
                buf = self.band_buffers[band_name]
                buf.extend(band_signal[-new_samples.size:].tolist())
                if len(buf) > config.BUFFER_SIZE:
                    self.band_buffers[band_name] = buf[-config.BUFFER_SIZE:]

    # ------------------------------------------------------------------ #
    def render(self):
        if not self.running or not self.raw_buffer:
            return

        plt.clf()
        plt.subplot(len(PLOT_BANDS) + 1, 1, 1)
        plt.plot(self.raw_buffer[-250:], color="black")
        plt.title("Raw EEG waveform")
        plt.grid(True)

        colors = {"alpha": "tab:blue", "beta": "tab:green", "gamma": "tab:red"}
        for idx, band_name in enumerate(PLOT_BANDS, start=2):
            data = self.band_buffers.get(band_name, [])
            plt.subplot(len(PLOT_BANDS) + 1, 1, idx)
            plt.plot(data[-250:], color=colors.get(band_name, "tab:gray"))
            low, high = config.FREQUENCY_BANDS[band_name]
            plt.title(f"{band_name.upper()} band ({low}-{high} Hz)")
            plt.grid(True)

        plt.tight_layout()
        plt.pause(config.PLOT_REFRESH_S)

    # ------------------------------------------------------------------ #
    def compute_metrics(self) -> dict[str, float]:
        signal = np.asarray(self.raw_buffer, dtype=np.float32)
        if signal.size == 0:
            return {}
        decomposed = self.processor.decompose_bands(signal)
        return self.feature_extractor.extract_all_features(signal, decomposed)

    def maybe_log_metrics(self):
        now = time.time()
        if now - self._last_metrics_log < 2.0:
            return
        self._last_metrics_log = now
        metrics = self.compute_metrics()
        if metrics:
            logger.info(
                "metrics: peak_freq=%.2f engagement=%.3f power_alpha=%.3g "
                "power_beta=%.3g power_gamma=%.3g",
                metrics.get("peak_freq", 0.0),
                metrics.get("engagement_index", 0.0),
                metrics.get("power_alpha", 0.0),
                metrics.get("power_beta", 0.0),
                metrics.get("power_gamma", 0.0),
            )

    # ------------------------------------------------------------------ #
    def save_session(self, filename=config.HDF5_FILENAME):
        signal = np.asarray(self.raw_buffer, dtype=np.float32)
        bands = {
            name: np.asarray(self.band_buffers.get(name, []), dtype=np.float32)
            for name in config.FREQUENCY_BANDS.keys()
        }
        payload = {"raw": signal, **bands}
        try:
            self.data_manager.save_to_hdf5(payload, filename)
            self.data_manager.export_csv(payload)
        except Exception as exc:
            logger.error("Failed to save session: %s", exc)

    # ------------------------------------------------------------------ #
    def run(self):
        if not self.connect():
            logger.error("Could not connect to serial device. "
                         "Check COM port and device status.")
            return

        plt.figure(figsize=config.WINDOW_SIZE)
        logger.info("EEG acquisition started. Press Ctrl+C to stop.")
        try:
            while True:
                self.update()
                self.render()
                self.maybe_log_metrics()
                time.sleep(config.PLOT_REFRESH_S)
        except KeyboardInterrupt:
            logger.info("User stopped EEG acquisition")
        finally:
            self.save_session()
            self.disconnect()
            plt.close("all")


if __name__ == "__main__":
    EEGAnalyzerApp().run()

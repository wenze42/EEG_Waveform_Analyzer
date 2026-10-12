"""Live band-separated EEG viewer (delta/theta/alpha/beta/gamma).

Uses the threaded SerialEEGReader and SignalProcessor so the displayed
bands are computed consistently with the rest of the library.
"""

from __future__ import annotations

import time

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt

import config
from serial_reader import SerialEEGReader
from signal_processor import SignalProcessor

VIEW_SAMPLES = 512     # ~2 s window at 250 Hz - enough for low-band filtering
BAND_COLORS = {
    "delta": "purple",
    "theta": "orange",
    "alpha": "tab:blue",
    "beta": "tab:green",
    "gamma": "tab:red",
}


def main():
    reader = SerialEEGReader(
        port=config.SERIAL_PORT, baudrate=config.SERIAL_BAUD,
        timeout=config.SERIAL_TIMEOUT,
    )
    if not reader.open():
        raise SystemExit("Failed to open serial port")
    reader.start_reading()

    proc = SignalProcessor(fs=config.SAMPLING_RATE)
    bands = list(config.FREQUENCY_BANDS.keys())

    plt.figure(figsize=(12, 10))
    try:
        while True:
            data = reader.get_latest(VIEW_SAMPLES)
            if data.size < 50:
                time.sleep(0.05)
                continue

            decomposed = proc.decompose_bands(data)

            plt.clf()
            plt.subplot(len(bands) + 1, 1, 1)
            plt.plot(data, color="black")
            plt.title("Raw EEG")
            plt.grid(True)

            for idx, band in enumerate(bands, start=2):
                low, high = config.FREQUENCY_BANDS[band]
                plt.subplot(len(bands) + 1, 1, idx)
                plt.plot(decomposed[band],
                         color=BAND_COLORS.get(band, "tab:gray"))
                plt.title(f"{band.capitalize()} ({low}-{high} Hz)")
                plt.grid(True)

            plt.tight_layout()
            plt.pause(0.02)
    except KeyboardInterrupt:
        pass
    finally:
        reader.close()


if __name__ == "__main__":
    main()

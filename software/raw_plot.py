"""Minimal live raw-waveform viewer.

Uses the threaded SerialEEGReader so it stays compatible with the binary
frame protocol emitted by the firmware. Good for quickly verifying that
the device is sampling and that the link is healthy.
"""

from __future__ import annotations

import time

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt

import config
from serial_reader import SerialEEGReader

VIEW_SAMPLES = 250


def main():
    reader = SerialEEGReader(
        port=config.SERIAL_PORT, baudrate=config.SERIAL_BAUD,
        timeout=config.SERIAL_TIMEOUT,
    )
    if not reader.open():
        raise SystemExit("Failed to open serial port")

    reader.start_reading()
    plt.figure(figsize=(12, 6))
    plt.title("Raw EEG waveform")
    plt.xlabel("Sample index")
    plt.ylabel("Amplitude")

    try:
        while True:
            data = reader.get_latest(VIEW_SAMPLES)
            if data.size == 0:
                time.sleep(0.05)
                continue
            plt.cla()
            plt.plot(data, color="black")
            plt.title("Raw EEG waveform")
            plt.xlabel("Sample index")
            plt.ylabel("Amplitude")
            plt.grid(True)
            plt.pause(0.01)
    except KeyboardInterrupt:
        pass
    finally:
        reader.close()


if __name__ == "__main__":
    main()

"""Central configuration for the EEG monitor application."""

import os

# ----- Serial / device -------------------------------------------------------
SERIAL_PORT = os.environ.get("EEG_PORT", "COM3")   # /dev/ttyUSB0 on Linux/macOS
SERIAL_BAUD = 115200
SERIAL_TIMEOUT = 1

# ----- Acquisition -----------------------------------------------------------
SAMPLING_RATE = 250            # Hz - must match firmware TIM3 config
BUFFER_SIZE = 1024             # rolling sample buffer length
FRAME_HEADER = b"\xAA\x55"     # 2-byte sync header emitted by firmware
FRAME_MAX_SAMPLES = 16         # samples per binary packet

# ----- Frequency bands (Hz) --------------------------------------------------
FREQUENCY_BANDS = {
    "delta": (0.5, 4.0),
    "theta": (4.0, 8.0),
    "alpha": (8.0, 12.0),
    "beta":  (12.0, 30.0),
    "gamma": (30.0, 80.0),
}

NOTCH_FREQ = 50.0              # power-line interference notch (use 60.0 in US/JP)
NOTCH_Q = 30.0

# ----- Visualization ---------------------------------------------------------
WINDOW_SIZE = (12, 8)
PLOT_REFRESH_S = 0.05

# ----- Persistence -----------------------------------------------------------
DATA_DIR = os.environ.get(
    "EEG_DATA_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data"),
)
HDF5_FILENAME = "latest_session.h5"
CSV_FILENAME = "latest_session.csv"

# ----- Logging ---------------------------------------------------------------
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

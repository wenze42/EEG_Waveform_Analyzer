"""Persistence layer for EEG sessions (HDF5 + CSV export).

The data manager stores the raw signal and band-decomposed signals in an
HDF5 file with per-dataset timestamps, and provides a convenience CSV
export of summary metrics alongside the raw values.
"""

from __future__ import annotations

import os
from datetime import datetime

import h5py
import numpy as np
import pandas as pd

import config
from logger import logger


def _ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


class EEGDataManager:
    def __init__(self, data_dir: str = config.DATA_DIR):
        self.data_dir = _ensure_dir(data_dir)

    # ------------------------------------------------------------------ #
    #  HDF5                                                              #
    # ------------------------------------------------------------------ #
    def save_to_hdf5(self, payload: dict, filename: str = config.HDF5_FILENAME):
        path = os.path.join(self.data_dir, filename)
        ts = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        with h5py.File(path, "w") as h5:
            grp = h5.create_group("eeg")
            grp.attrs["created_at"] = ts
            grp.attrs["sampling_rate"] = config.SAMPLING_RATE
            grp.attrs["bands"] = ",".join(config.FREQUENCY_BANDS.keys())
            for name, array in payload.items():
                arr = np.asarray(array, dtype=np.float32)
                grp.create_dataset(name, data=arr, compression="gzip")
        logger.info("Saved session to %s", path)
        return path

    def load_from_hdf5(self, filename: str = config.HDF5_FILENAME) -> dict:
        path = os.path.join(self.data_dir, filename)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Session file not found: {path}")
        with h5py.File(path, "r") as h5:
            grp = h5["eeg"]
            return {name: grp[name][...] for name in grp.keys()}

    # ------------------------------------------------------------------ #
    #  CSV                                                               #
    # ------------------------------------------------------------------ #
    def export_csv(self, payload: dict, filename: str = config.CSV_FILENAME):
        path = os.path.join(self.data_dir, filename)
        columns = {}
        max_len = 0
        for name, array in payload.items():
            arr = np.asarray(array).ravel()
            columns[name] = arr
            max_len = max(max_len, arr.size)

        rows = {}
        for name, arr in columns.items():
            padded = np.full(max_len, np.nan, dtype=np.float64)
            padded[: arr.size] = arr.astype(np.float64)
            rows[name] = padded
        rows["sample_index"] = np.arange(max_len)

        df = pd.DataFrame(rows)
        df.to_csv(path, index=False)
        logger.info("Exported CSV to %s", path)
        return path

    def list_sessions(self) -> list[str]:
        if not os.path.isdir(self.data_dir):
            return []
        return sorted(
            f for f in os.listdir(self.data_dir)
            if f.endswith(".h5") or f.endswith(".hdf5")
        )

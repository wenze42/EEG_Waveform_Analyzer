"""Threaded serial reader for the EEG firmware binary stream protocol.

Frame layout (little-endian):
    [0xAA][0x55][seq:u16][count:u16][samples:count * i16][crc8]

A background thread pulls bytes from the serial port, reassembles frames,
verifies the CRC8 and pushes the decoded int16 samples onto a thread-safe
ring buffer. The UI/analysis thread consumes them via get_latest().
"""

from __future__ import annotations

import struct
import threading
import time
from collections import deque

import numpy as np
import serial

import config
from logger import logger

_FRAME_HEADER = config.FRAME_HEADER        # b"\xAA\x55"
_HEADER_LEN = 6                            # 2 sync + 2 seq + 2 count
_CRC_LEN = 1
_MAX_SAMPLES_PER_FRAME = 256               # safety bound


def _crc8(data: bytes) -> int:
    crc = 0x00
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ 0x07) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc


class SerialEEGReader:
    def __init__(self, port: str = config.SERIAL_PORT,
                 baudrate: int = config.SERIAL_BAUD,
                 timeout: float = config.SERIAL_TIMEOUT,
                 buffer_size: int = config.BUFFER_SIZE):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.buffer_size = buffer_size

        self.ser: serial.Serial | None = None
        self._buffer: deque[int] = deque(maxlen=buffer_size)
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._running = threading.Event()
        # In-flight byte stream for frame assembly.
        self._rx_bytes = bytearray()
        self.frames_received = 0
        self.frames_dropped = 0

    # ------------------------------------------------------------------ #
    #  Connection management                                             #
    # ------------------------------------------------------------------ #
    def open(self) -> bool:
        try:
            self.ser = serial.Serial(
                self.port, self.baudrate, timeout=self.timeout
            )
            time.sleep(0.5)
            logger.info("Serial connected: %s @ %d baud", self.port, self.baudrate)
            return True
        except Exception as exc:
            logger.error("Cannot open serial port %s: %s", self.port, exc)
            self.ser = None
            return False

    def close(self):
        self.stop_reading()
        if self.ser is not None:
            self.ser.close()
            self.ser = None
            logger.info("Serial port closed")

    # ------------------------------------------------------------------ #
    #  Background reader                                                 #
    # ------------------------------------------------------------------ #
    def start_reading(self):
        if self._thread and self._thread.is_alive():
            return
        if self.ser is None:
            raise RuntimeError("Serial port is not open")
        self._running.set()
        self._thread = threading.Thread(
            target=self._read_loop, name="eeg-serial", daemon=True
        )
        self._thread.start()

    def stop_reading(self):
        self._running.clear()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _read_loop(self):
        while self._running.is_set() and self.ser is not None:
            try:
                chunk = self.ser.read(64)
            except Exception as exc:
                logger.error("Serial read error: %s", exc)
                time.sleep(0.1)
                continue
            if not chunk:
                continue
            self._rx_bytes.extend(chunk)
            self._consume_frames()

    # ------------------------------------------------------------------ #
    #  Frame reassembly                                                  #
    # ------------------------------------------------------------------ #
    def _consume_frames(self):
        while True:
            frame = self._try_extract_frame()
            if frame is None:
                break
            seq, count, samples, crc_ok = frame
            if not crc_ok:
                self.frames_dropped += 1
                logger.debug("Bad CRC on frame seq=%d", seq)
                continue
            self.frames_received += 1
            with self._lock:
                self._buffer.extend(samples.tolist())

    def _try_extract_frame(self):
        # Align to header: drop leading bytes until 0xAA 0x55 found.
        while True:
            if len(self._rx_bytes) < 2:
                return None
            if self._rx_bytes[0] == _FRAME_HEADER[0] and \
               self._rx_bytes[1] == _FRAME_HEADER[1]:
                break
            del self._rx_bytes[0]

        if len(self._rx_bytes) < _HEADER_LEN:
            return None

        seq, count = struct.unpack_from("<HH", self._rx_bytes, 2)
        if count == 0 or count > _MAX_SAMPLES_PER_FRAME:
            # Corrupt length field - drop header and resync.
            del self._rx_bytes[:2]
            return None

        total_len = _HEADER_LEN + count * 2 + _CRC_LEN
        if len(self._rx_bytes) < total_len:
            return None

        payload = bytes(self._rx_bytes[:total_len - _CRC_LEN])
        crc_recv = self._rx_bytes[total_len - _CRC_LEN]
        crc_calc = _crc8(payload)
        samples = np.frombuffer(
            payload[_HEADER_LEN:], dtype="<i2", count=count
        ).astype(np.int16)

        del self._rx_bytes[:total_len]
        return seq, count, samples, (crc_recv == crc_calc)

    # ------------------------------------------------------------------ #
    #  Public data access                                                #
    # ------------------------------------------------------------------ #
    def get_latest(self, n: int = config.BUFFER_SIZE) -> np.ndarray:
        """Return up to the n most recent samples as an int16 numpy array.

        Non-destructive peek - samples stay in the buffer.
        """
        with self._lock:
            if not self._buffer:
                return np.empty(0, dtype=np.int16)
            take = min(n, len(self._buffer))
            data = list(self._buffer)[-take:]
        return np.asarray(data, dtype=np.int16)

    def drain_new_samples(self) -> np.ndarray:
        """Return and remove all samples accumulated since the last drain.

        Use this in the consumer loop to avoid duplicating data across
        successive UI updates when sampling is faster than rendering.
        """
        with self._lock:
            if not self._buffer:
                return np.empty(0, dtype=np.int16)
            data = list(self._buffer)
            self._buffer.clear()
        return np.asarray(data, dtype=np.int16)

    def read_samples(self, count: int = config.BUFFER_SIZE) -> np.ndarray:
        return self.get_latest(count)

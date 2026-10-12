"""
EEG application entry point.
Reads serial data, analyzes signal bands, visualizes the waveform, and exports metrics.
"""

import os
import time

import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import numpy as np

import config
from data_manager import EEGDataManager
from feature_extractor import FeatureExtractor
from logger import logger
from serial_reader import SerialEEGReader
from signal_processor import SignalProcessor


class EEGAnalyzerApp:
    def __init__(self, port=config.SERIAL_PORT, baudrate=config.SERIAL_BAUD):
        self.serial = SerialEEGReader(port=port, baudrate=baudrate, timeout=config.SERIAL_TIMEOUT)
        self.processor = SignalProcessor(fs=config.SAMPLING_RATE)
        self.feature_extractor = FeatureExtractor(fs=config.SAMPLING_RATE)
        self.data_manager = EEGDataManager(data_dir=config.DATA_DIR)
        self.raw_buffer = []
        self.band_buffers = {name: [] for name in config.FREQUENCY_BANDS.keys()}
        self.running = False

    def connect(self):
        if not self.serial.open():
            return False
        self.running = True
        self.serial.start_reading()
        return True

    def disconnect(self):
        self.running = False
        self.serial.stop_reading()
        self.serial.close()

    def update(self):
        if not self.running:
            return

        latest = self.serial.get_latest(n=250)
        if latest.size == 0:
            return

        self.raw_buffer.extend(latest.tolist())
        if len(self.raw_buffer) > config.BUFFER_SIZE:
            self.raw_buffer = self.raw_buffer[-config.BUFFER_SIZE:]

        signal = np.asarray(self.raw_buffer, dtype=np.float32)
        if signal.size > 50:
            decomposed = self.processor.decompose_bands(signal)
            for band_name, band_signal in decomposed.items():
                self.band_buffers[band_name].extend(band_signal.tolist())
                if len(self.band_buffers[band_name]) > config.BUFFER_SIZE:
                    self.band_buffers[band_name] = self.band_buffers[band_name][-config.BUFFER_SIZE:]

    def render(self):
        if not self.running:
            return

        plt.clf()
        plt.subplot(5, 1, 1)
        plt.plot(self.raw_buffer[-250:], color='black')
        plt.title('Raw EEG waveform')
        plt.grid(True)

        for idx, band_name in enumerate(['alpha', 'beta', 'gamma'], start=2):
            data = self.band_buffers.get(band_name, [])
            plt.subplot(5, 1, idx)
            plt.plot(data[-250:], color='tab:blue' if band_name == 'alpha' else 'tab:green' if band_name == 'beta' else 'tab:red')
            plt.title(f'{band_name.upper()} band')
            plt.grid(True)

        plt.tight_layout()
        plt.pause(0.05)

    def compute_metrics(self):
        signal = np.asarray(self.raw_buffer, dtype=np.float32)
        if signal.size == 0:
            return {}

        decomposed = self.processor.decompose_bands(signal)
        features = self.feature_extractor.extract_all_features(signal, decomposed)
        return features

    def save_session(self, filename='latest_session.h5'):
        signal = np.asarray(self.raw_buffer, dtype=np.float32)
        bands = {band_name: np.asarray(self.band_buffers.get(band_name, []), dtype=np.float32)
                 for band_name in config.FREQUENCY_BANDS.keys()}
        payload = {'raw': signal, **bands}
        return self.data_manager.save_to_hdf5(payload, filename)

    def run(self):
        if not self.connect():
            logger.error('Could not connect to serial device. Please check COM port and device status.')
            return

        plt.figure(figsize=config.WINDOW_SIZE)
        try:
            while True:
                self.update()
                self.render()
                time.sleep(0.05)
        except KeyboardInterrupt:
            logger.info('User stopped EEG acquisition')
        finally:
            self.save_session()
            self.disconnect()
            plt.close('all')


if __name__ == '__main__':
    app = EEGAnalyzerApp()
    app.run()

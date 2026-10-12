# EEG Waveform Analyzer

This project is a lightweight EEG monitoring demo based on STM32 + Python. It streams raw ADC samples from the STM32 to the PC, then displays the raw waveform and optionally filters the signal into alpha (8–12 Hz), beta (12–30 Hz), and gamma (30–100 Hz) bands.

## Features
- STM32 ADC sampling at ~250 Hz
- UART transmission to PC
- Real-time raw waveform display
- Real-time alpha/beta/gamma band separation
- FFT-based analysis support
- CSV export support

## Hardware
- STM32F103C8T6
- AD8232 analog front-end
- USB-TTL serial adapter
- EEG electrodes and reference lead

## Software
- Python 3.10+
- numpy
- scipy
- matplotlib
- pyserial

## Quick start
```bash
cd software
pip install -r requirements.txt
python raw_plot.py
```

For the full band-separated view:
```bash
python eeg_analysis.py
```

## Recommended pin mapping
- ADC input: PA0 (ADC1_IN0)
- UART TX: PA9
- UART RX: PA10

## Notes
This project is intended for learning and demonstration. It is not a medical-grade EEG system.

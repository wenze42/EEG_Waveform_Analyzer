# EEG Waveform Analyzer

This project is a lightweight EEG monitoring demo for STM32 + Python. It streams raw ADC samples from the MCU to the PC, then separates EEG components into alpha (8–12 Hz), beta (12–30 Hz), and gamma (30–100 Hz) bands in real time.

## Features
- STM32 ADC sampling at ~250 Hz
- UART transmission to PC
- Real-time raw waveform display
- Alpha/beta/gamma band separation using digital filtering
- FFT-based frequency visualization
- CSV export support

## Hardware
- STM32F103C8T6
- AD8232 or any low-noise analog front-end
- UART serial connection to PC

## Software
- Python 3.10+
- scipy, numpy, matplotlib, pyserial

## Quick start
```bash
cd software
pip install -r requirements.txt
python eeg_app.py
```

## STM32 pin example
- ADC: PA0 (ADC1_IN0)
- UART TX: PA9
- UART RX: PA10

## Notes
This is a teaching/demo project and is not a clinical EEG system.

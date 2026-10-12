# EEG Waveform Analyzer (ADS1291 Version)

This project is a lightweight EEG monitoring demo based on STM32 + ADS1291 + Python. It streams raw 24-bit samples from the ADS1291 via SPI to the STM32, then over UART to the PC, and displays the raw waveform with real-time alpha (8–12 Hz), beta (12–30 Hz), and gamma (30–80 Hz) band separation.

## Features
- STM32 SPI interface to ADS1291 24-bit ADC
- 250 SPS sampling rate (software configurable)
- UART transmission to PC (115200 baud)
- Real-time raw waveform display
- Real-time delta/theta/alpha/beta/gamma band separation
- FFT-based analysis support
- CSV and HDF5 export support

## Hardware
- STM32F103C8T6 (Blue Pill)
- ADS1291 24-bit EEG analog front-end module
- USB-TTL serial adapter
- EEG electrodes and reference lead

## Software
- Python 3.10+
- numpy
- scipy
- matplotlib
- pyserial
- h5py
- pandas

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
- SPI1 NSS: PA4 (ADS1291 CS)
- SPI1 SCK: PA5 (ADS1291 SCLK)
- SPI1 MISO: PA6 (ADS1291 DOUT)
- SPI1 MOSI: PA7 (ADS1291 DIN)
- EXTI3: PA3 (ADS1291 DRDY)
- UART TX: PA9
- UART RX: PA10

## ADS1291 register configuration
- CONFIG1: 0x02 (250 SPS)
- CH1SET: 0x06 (gain = 6, normal electrode)
- Built-in 50Hz/60Hz notch filter

## Notes
This project is intended for learning and demonstration. It is not a medical-grade EEG system. Always use isolated power when connecting electrodes to a person.

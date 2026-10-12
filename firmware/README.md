# EEG Monitor Firmware (ADS1291 Version)

STM32F103C8T6 firmware that samples a single EEG channel via **ADS1291** 24-bit ADC at **250 SPS** and streams framed samples to the host PC over USART1 @ 115200 baud.

## Sampling pipeline

```
电极 → ADS1291 (INP/INN 差分输入, RLD 右腿驱动)
         ↓ SPI1 (1.125 MHz)
STM32F103C8T6 (DRDY 下降沿中断 → 读取 24-bit 样本)
         ↓ USART1 TX (PA9)
USB-TTL 适配器 → PC
```

### Packet format (binary, little-endian)

| Offset | Field  | Type   | Notes                                |
|--------|--------|--------|--------------------------------------|
| 0      | sync0  | u8     | 0xAA                                 |
| 1      | sync1  | u8     | 0x55                                 |
| 2..3   | seq    | u16 LE | increments per packet                |
| 4..5   | count  | u16 LE | number of int32 samples (<=8)        |
| 6..    | data   | i32[]  | `count` little-endian int32 samples  |
| end-1  | crc8   | u8     | CRC-8 (poly 0x07) over all preceding |

**Sample value**: 24-bit signed two's complement, sign-extended to 32-bit.
Range: `-8,388,608` to `+8,388,607`. To convert to voltage:
```
V = (sample / 2^23) * Vref / gain
```
Where `Vref = 2.4V` (external) and `gain = 6` (default).

## Bill of materials (器件清单)

| # | Part                       | Spec / value                          | Qty | Notes                                           |
|---|----------------------------|---------------------------------------|-----|-------------------------------------------------|
| 1 | Microcontroller            | STM32F103C8T6 (Blue Pill)             | 1   | 72 MHz, SPI1, USART1                            |
| 2 | Analog front-end           | ADS1291 module                        | 1   | 24-bit EEG AFE, built-in RLD + notch filter    |
| 3 | EEG electrodes             | Ag/AgCl cup or disposable             | 3   | RA, LA, RL (or 1 signal + 1 ref + 1 driven)     |
| 4 | Electrode lead wire set    | snap or DIN, shielded                 | 1   | ~1 m, matches electrode connectors              |
| 5 | Conductive gel             | Ten20 or equivalent                   | 1   | Improve skin contact                            |
| 6 | USB-TTL serial adapter     | CP2102 / CH340 / FT232                 | 1   | 3.3 V logic, 115200 baud                        |
| 7 | Power source               | USB 5 V or 3.3 V LDO board             | 1   | STM32 + ADS1291 can run from USB                 |
| 8 | Decoupling caps            | 100 nF + 10 µF                        | 2   | Across ADS1291 DVDD/DGND                        |
| 9 | Reference capacitor        | 10 µF tantalum or ceramic             | 1   | Across VREFP/VREFN (if using external ref)       |
| 10| LED (status)               | PC13 onboard LED                      | 1   | Blue Pill already has this                       |

> ADS1291 is a **medical-grade** analog front-end specifically designed for
> EEG applications. It is safe for learning purposes when powered from a
> floating source (battery or isolated USB). Always use a medically isolated
> power supply when connecting electrodes to a person.

## Wiring (Blue Pill + ADS1291 module)

### Power & ground

| STM32F103C8T6 | ADS1291 module | Function              |
|---------------|----------------|-----------------------|
| 3V3           | DVDD           | Digital supply        |
| GND           | DGND           | Digital ground        |
| 3.3V LDO      | AVDD           | Analog supply (2.7-5.25V) |
| GND           | AGND           | Analog ground         |
| 3.3V LDO      | VREFP          | Reference positive    |
| GND           | VREFN          | Reference negative    |

### SPI interface

| STM32F103C8T6 | ADS1291 module | Function              |
|---------------|----------------|-----------------------|
| PA4 (SPI1_NSS)  | CS             | Chip select (active low) |
| PA5 (SPI1_SCK)  | SCLK           | SPI clock             |
| PA6 (SPI1_MISO) | DOUT           | Data output (ADS1291 → STM32) |
| PA7 (SPI1_MOSI) | DIN            | Data input (STM32 → ADS1291) |
| PA3 (EXTI3)     | DRDY           | Data ready (falling edge) |

### UART interface

| STM32F103C8T6 | USB-TTL adapter | Function              |
|---------------|-----------------|-----------------------|
| PA9 (USART1_TX) | RXD           | MCU → PC data         |
| PA10 (USART1_RX)| TXD           | Optional (no RX use)  |
| PC13          | onboard LED     | 250 Hz packet blink   |

### Electrode connections

| ADS1291 module | Electrode | Function              |
|----------------|-----------|-----------------------|
| IN1P (INP)     | RA        | Right arm (positive)  |
| IN1N (INN)     | LA        | Left arm (negative)   |
| RLD (RL)       | RL        | Right leg (driven reference) |

For better alpha detection, place LA on the occipital region (O1/O2).

## ADS1291 register configuration

The firmware configures the following registers at startup:

| Register | Address | Value | Description                          |
|----------|---------|-------|--------------------------------------|
| CONFIG1  | 0x01    | 0x02  | DR = 250 SPS, CLK = 2.048 MHz        |
| CONFIG2  | 0x02    | 0x00  | RLD off, normal mode                 |
| CONFIG3  | 0x03    | 0x00  | External reference                   |
| CH1SET   | 0x04    | 0x06  | Gain = 6, normal electrode input     |
| CH2SET   | 0x05    | 0x01  | Power down (unused channel)          |

### Adjustable parameters (software configurable)

| Parameter | Register | Value range | Effect                               |
|-----------|----------|-------------|--------------------------------------|
| Gain      | CH1SET   | 0x00-0x07   | 1, 2, 4, 6, 8, 12, 24 (×Vref)        |
| Sample rate| CONFIG1 | 0x00-0x07   | 250, 500, 1k, 2k, 4k, 8k, 16k SPS    |
| Notch filter| CONFIG2 | bit 6       | 50Hz/60Hz notch (enable/disable)     |
| RLD       | CONFIG2  | bit 5       | Right-leg drive (enable/disable)     |

## Build

This firmware assumes STM32Cube HAL. Recommended build paths:

1. **STM32CubeIDE** - create a project for STM32F103C8Tx, enable HSE, set
   SYSCLK to 72 MHz (HSE 8 MHz x PLL9), add `main.c` from this folder.
2. **Makefile + arm-none-eabi-gcc** - use the STM32CubeF1 HAL package and
   include `main.c` as the application source.

Required HAL modules:
- `stm32f1xx_hal_rcc`, `stm32f1xx_hal_gpio`
- `stm32f1xx_hal_spi`
- `stm32f1xx_hal_uart`
- `stm32f1xx_hal_exti`

### Tweakable constants

| Macro / symbol      | Default | Effect                                |
|---------------------|---------|---------------------------------------|
| `SPI1` baud rate    | 1.125 MHz | SPI clock speed                      |
| `FRAME_MAX_SAMPLES` | 8       | Samples packed per UART frame         |
| `SAMPLE_RATE_HZ`    | 250     | ADS1291 sample rate (CONFIG1 DR bits) |

## Notes / safety

- This project is for **learning and demonstration only**. It is not a
  medical-grade EEG system.
- Connect electrodes to a human only with a fully floating power source
  (battery or medically isolated supply). Never use mains-powered
  equipment without isolation.
- The 50 Hz notch filter is **built into ADS1291** (CONFIG2 bit 6) and can be
  enabled/disabled via software. No host-side notch filter is needed.
- ADS1291 provides **24-bit resolution**, which is sufficient to capture
  δ (0.5-4 Hz), θ (4-8 Hz), α (8-12 Hz), β (12-30 Hz), and γ (30-80 Hz)
  bands without additional analog filtering.

# EEG Monitor Firmware

STM32F103C8T6 firmware that samples a single EEG channel at **250 Hz** and
streams framed samples to the host PC over USART1 @ 115200 baud.

## Sampling pipeline

```
AD8232 OUT --PA0--> ADC1_IN0
                    |
   TIM3 (250 Hz TRGO) triggers conversion
                    |
              EOC IRQ -> ring buffer (SPSC, 256 slots)
                    |
              main loop packs 16 samples into a framed packet
                    |
              USART1 TX (PA9) -> USB-TTL adapter -> PC
```

### Packet format (binary, little-endian)

| Offset | Field  | Type   | Notes                                |
|--------|--------|--------|--------------------------------------|
| 0      | sync0  | u8     | 0xAA                                 |
| 1      | sync1  | u8     | 0x55                                 |
| 2..3   | seq    | u16 LE | increments per packet                |
| 4..5   | count  | u16 LE | number of int16 samples (<=16)        |
| 6..    | data   | i16[]  | `count` little-endian int16 samples  |
| end-1  | crc8   | u8     | CRC-8 (poly 0x07) over all preceding |

Sample value: `(raw_adc - 2048) * 8`, so the int16 range roughly maps the
full ADC swing with headroom. On the host, divide by 8 to recover the
centered 12-bit value.

## Bill of materials (器件清单)

| # | Part                       | Spec / value                          | Qty | Notes                                           |
|---|----------------------------|---------------------------------------|-----|-------------------------------------------------|
| 1 | Microcontroller            | STM32F103C8T6 (Blue Pill)             | 1   | 72 MHz, 12-bit ADC, USART1                      |
| 2 | Analog front-end           | AD8232 heart-rate/EEG AFE             | 1   | Single-supply, instrument amp + HP/LP filters    |
| 3 | EEG electrodes             | Ag/AgCl cup or disposable             | 3   | RA, LA, RL (or 1 signal + 1 ref + 1 driven)     |
| 4 | Electrode lead wire set    | snap or DIN, shielded                 | 1   | ~1 m, matches electrode connectors              |
| 5 | Conductive gel             | Ten20 or equivalent                   | 1   | Improve skin contact                            |
| 6 | USB-TTL serial adapter     | CP2102 / CH340 / FT232                 | 1   | 3.3 V logic, 115200 baud                         |
| 7 | Power source               | USB 5 V or 3.3 V LDO board             | 1   | STM32 + AD8232 can run from USB                  |
| 8 | Decoupling caps            | 100 nF + 10 uF                        | 2   | Across AD8232 Vcc/GND                            |
| 9 | LED (status)               | PC13 onboard LED                      | 1   | Blue Pill already has this                       |
| 10| Resistor (optional)        | 10 kOhm                               | 1   | MCU BOOT0 pull-down if reusing bare board        |

> AD8232 is biologically safe for learning purposes. It is **not** a medical-
> grade device. Always power from a floating source (battery or isolated USB)
> when connecting electrodes to a person.

## Wiring (Blue Pill + AD8232)

| STM32F103C8T6 | AD8232 / adapter | Function              |
|---------------|------------------|-----------------------|
| 3V3           | 3.3V (pin 3)     | AFE supply            |
| GND           | GND (pin 2)      | Common ground         |
| PA0 / ADC1_IN0| OUTPUT (pin 1)   | EEG signal            |
| 5V (USB)      | 3.3V LDO input   | Power chain           |
| PA9  (USART1_TX)| USB-TTL RXD    | MCU -> PC data        |
| PA10 (USART1_RX)| USB-TTL TXD    | Optional (no RX use)  |
| PC13          | onboard LED      | 250 Hz packet blink   |

AD8232 electrode placement (Einthoven-like, single channel):
- **RA** - right arm
- **LA** - left arm (or occipital for visual cortex alpha)
- **RL** - right leg (driven reference)

For better alpha detection, place LA on the occipital region (O1/O2).

## Build

This firmware assumes STM32Cube HAL. Recommended build paths:

1. **STM32CubeIDE** - create a project for STM32F103C8Tx, enable HSE, set
   SYSCLK to 72 MHz (HSE 8 MHz x PLL9), add `main.c` from this folder.
2. **Makefile + arm-none-eabi-gcc** - use the STM32CubeF1 HAL package and
   include `main.c` as the application source.

Required HAL modules:
- `stm32f1xx_hal_rcc`, `stm32f1xx_hal_gpio`
- `stm32f1xx_hal_adc` (and `stm32f1xx_hal_adc_ex` for calibration)
- `stm32f1xx_hal_uart`
- `stm32f1xx_hal_tim` (and `_ex` for TRGO config)

### Tweakable constants

| Macro / symbol      | Default | Effect                                |
|---------------------|---------|---------------------------------------|
| `TIM3` PSC/ARR      | 7199/39 | 250 Hz sampling (10 kHz / 40)         |
| `ADC_SAMPLETIME_*`  | 55.5 cy | ~1.5 us acquisition at 36 MHz          |
| `FRAME_MAX_SAMPLES` | 16      | Samples packed per UART frame         |
| `ADC_MID`           | 2048    | Mid-scale offset subtracted in IRQ    |

## Notes / safety

- This project is for **learning and demonstration only**. It is not a
  medical-grade EEG system.
- Connect electrodes to a human only with a fully floating power source
  (battery or medically isolated supply). Never use mains-powered
  equipment without isolation.
- The 50 Hz notch and 0.5 Hz high-pass filters run on the host side
  (`software/signal_processor.py`).

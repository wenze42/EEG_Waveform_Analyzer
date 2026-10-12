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

## Wiring (Blue Pill + AD8232 Heart Monitor breakout)

> ⚠️ **SDN 必须接 3V3** — AD8232 的 SDN 引脚是使能脚,低电平时芯片睡眠
> 完全不输出,这是最常见的接错点。板子丝印从上到下依次为:
> `GND | 3.3v | OUTPUT | LO- | LO+ | SDN`,上方另有 `RL | LA | RA` 电极插口。

| STM32F103C8T6 | AD8232 breakout | 说明                                |
|---------------|-----------------|-------------------------------------|
| 3V3           | **3.3v**        | 模块供电 (板载 LDO 给芯片)          |
| 3V3           | **SDN**         | 使能脚拉高,否则芯片睡眠无输出       |
| GND           | **GND**         | 必须共地                            |
| PA0 / ADC1_IN0| **OUTPUT**      | 唯一采样信号                        |
| 悬空          | LO- / LO+       | 导联脱落检测,本项目不用             |
| 5V (USB)      | 3.3V LDO 输入   | 板载 LDO 也可由 5V 供电(可选)       |
| PA9 (USART1_TX)| USB-TTL RXD    | MCU -> PC 数据                      |
| PA10 (USART1_RX)| USB-TTL TXD    | 可选(无 RX 用途)                    |
| PC13          | 板载 LED        | 每帧翻转状态指示                    |

AD8232 电极安放 (Einthoven 单通道):
- **RA** 插口 → 右臂电极
- **LA** 插口 → 左臂电极 (若检测视觉皮层 α 波,改放枕部 O1/O2)
- **RL** 插口 → 右腿电极 (驱动参考,抑制共模干扰)
- 电极先涂导电膏再贴,接触阻抗越低波形越好

### 电阻调参(可选,把心电 AFE 真正变成 EEG AFE)

出厂默认参数是心电拓扑,对 EEG 有两个硬伤。建议第一次先不改电阻跑通链路,
再按需调整:

| 目标 | 板上位置 | 默认值 | EEG 改值 | 效果 |
|------|----------|--------|----------|------|
| **增益 ×100 → ×500** | AD8232 芯片左上侧的 R5、R6 (两颗 10kΩ) | 10 kΩ | **2.2 kΩ** | 放大倍数从 ~100× 提到 ~500×,才够驱动 10–100 μV 的 EEG 信号 |
| **高通 0.5 Hz → 0.1 Hz** | AD8232 芯片右下侧 R3 旁的 C1 电容 (10 µF) | 10 µF | **47 µF** | 高通截止频率从 ~0.5 Hz 降到 ~0.1 Hz,保留 δ 波 (0.5–4 Hz) 和深睡相关的慢波 |
| **电源去耦** | 模块 3.3V 和 GND 之间 | 板上已带 100nF+10µF | 板外再并联 **10 µH 磁珠 + 100 nF** | 减少电源线串入的 50/60 Hz 工频干扰 |

> 改电阻/电容需要镊子和焊锡。找不到板上元件时,推荐先用默认值跑起来验证
> 链路——α 波 (8–12 Hz) 在枕部闭眼时幅值相对最大,不调参也能看到。

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

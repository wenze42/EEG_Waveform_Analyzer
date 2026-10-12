/*
 * EEG Waveform Monitor - STM32F103C8T6 + ADS1291 firmware
 *
 * Sampling pipeline:
 *   ADS1291 (DRDY falling edge) -> EXTI -> SPI1 read 24-bit sample
 *   -> samples pushed to ring buffer -> main loop packs into framed packets
 *   -> USART1 TX @ 115200 baud to USB-TTL adapter
 *
 * Packet format (binary, little-endian):
 *   [0xAA][0x55][seq:u16][count:u16][samples:count * i32][crc8:u8]
 *
 * ADS1291 SPI interface:
 *   PA4  -> SPI1_NSS  (ADS1291 CS)
 *   PA5  -> SPI1_SCK  (ADS1291 SCLK)
 *   PA6  <- SPI1_MISO (ADS1291 DOUT)
 *   PA7  -> SPI1_MOSI (ADS1291 DIN)
 *   PA3  <- ADS1291 DRDY (falling edge interrupt)
 *   3V3  -> ADS1291 DVDD (digital supply)
 *   GND  -> ADS1291 DGND
 *   AVDD -> ADS1291 AVDD (analog supply, typically 2.7-5.25V)
 *   AGND -> ADS1291 AGND
 *   VREFP/ VREFN -> ADS1291 reference (internal or external)
 *
 * ADS1291 register configuration:
 *   CONFIG1 = 0x02 (DR = 250 SPS, CLK = 2.048 MHz)
 *   CONFIG2 = 0x00 (RLD off for single channel, normal mode)
 *   CONFIG3 = 0x00 (external reference)
 *   CH1SET  = 0x06 (gain = 6, input = normal electrode)
 *   CH2SET  = 0x01 (power down, unused)
 */

#include "stm32f1xx_hal.h"
#include <string.h>

/* ------------------------------------------------------------------ */
/*  Handles and globals                                                */
/* ------------------------------------------------------------------ */
SPI_HandleTypeDef hspi1;
UART_HandleTypeDef huart1;

#define SAMPLE_RATE_HZ      250U
#define FRAME_MAX_SAMPLES   8U              /* 8 samples per packet (32-bit) */
#define FRAME_HEADER0       0xAAU
#define FRAME_HEADER1       0x55U

static volatile uint16_t g_seq = 0;
static volatile int32_t  g_ring[256];       /* ring buffer of 32-bit samples */
static volatile uint16_t g_ring_head = 0;
static volatile uint16_t g_ring_tail = 0;
static volatile uint16_t g_ring_count = 0;
static volatile uint8_t  g_drdy_flag = 0;

/* ------------------------------------------------------------------ */
/*  Forward declarations                                               */
/* ------------------------------------------------------------------ */
void SystemClock_Config(void);
void SPI1_Init(void);
void UART_Init(void);
void GPIO_Init(void);
void Error_Handler(void);
void HAL_SPI_MspInit(SPI_HandleTypeDef *hspi);
void HAL_UART_MspInit(UART_HandleTypeDef *huart);
static uint8_t crc8(const uint8_t *data, uint16_t len);
static void ring_push(int32_t v);
static uint16_t ring_pop_batch(int32_t *out, uint16_t max);
static void send_frame(void);
static void led_toggle(void);
static int32_t ADS1291_ReadSample(void);
static void ADS1291_Init(void);
static void ADS1291_WriteReg(uint8_t addr, uint8_t val);
static uint8_t ADS1291_ReadReg(uint8_t addr);

/* ------------------------------------------------------------------ */
/*  Main                                                               */
/* ------------------------------------------------------------------ */
int main(void)
{
    HAL_Init();
    SystemClock_Config();

    GPIO_Init();
    SPI1_Init();
    UART_Init();

    /* Initialize ADS1291 */
    ADS1291_Init();

    /* Enable EXTI on PA3 (DRDY falling edge) */
    HAL_NVIC_SetPriority(EXTI3_IRQn, 0, 0);
    HAL_NVIC_EnableIRQ(EXTI3_IRQn);

    while (1) {
        if (g_drdy_flag) {
            g_drdy_flag = 0;
            int32_t sample = ADS1291_ReadSample();
            ring_push(sample);
        }

        if (g_ring_count >= FRAME_MAX_SAMPLES) {
            send_frame();
            led_toggle();
        }
    }
}

/* ------------------------------------------------------------------ */
/*  Clock configuration: HSE 8 MHz x PLL9 -> 72 MHz SYSCLK             */
/* ------------------------------------------------------------------ */
void SystemClock_Config(void)
{
    RCC_OscInitTypeDef RCC_OscInitStruct = {0};
    RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

    RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSE;
    RCC_OscInitStruct.HSEState = RCC_HSE_ON;
    RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
    RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSE;
    RCC_OscInitStruct.PLL.PLLMUL = RCC_PLL_MUL9;
    if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK) {
        Error_Handler();
    }

    RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK | RCC_CLOCKTYPE_SYSCLK |
                                  RCC_CLOCKTYPE_PCLK1 | RCC_CLOCKTYPE_PCLK2;
    RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
    RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
    RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV2;
    RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;
    if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_2) != HAL_OK) {
        Error_Handler();
    }
}

/* ------------------------------------------------------------------ */
/*  GPIO / peripheral MSP init                                         */
/* ------------------------------------------------------------------ */
void HAL_SPI_MspInit(SPI_HandleTypeDef *hspi)
{
    if (hspi->Instance != SPI1) {
        return;
    }

    __HAL_RCC_SPI1_CLK_ENABLE();
    __HAL_RCC_GPIOA_CLK_ENABLE();

    GPIO_InitTypeDef GPIO_InitStruct = {0};
    /* PA4 = NSS (output push-pull), PA5 = SCK, PA7 = MOSI (alternate push-pull)
       PA6 = MISO (input floating) */
    GPIO_InitStruct.Pin = GPIO_PIN_5 | GPIO_PIN_7;
    GPIO_InitStruct.Mode = GPIO_MODE_AF_PP;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);

    GPIO_InitStruct.Pin = GPIO_PIN_4;
    GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);

    GPIO_InitStruct.Pin = GPIO_PIN_6;
    GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
    GPIO_InitStruct.Pull = GPIO_NOPULL;
    HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);

    /* NSS high by default */
    HAL_GPIO_WritePin(GPIOA, GPIO_PIN_4, GPIO_PIN_SET);
}

void HAL_UART_MspInit(UART_HandleTypeDef *huart)
{
    if (huart->Instance != USART1) {
        return;
    }

    __HAL_RCC_USART1_CLK_ENABLE();
    __HAL_RCC_GPIOA_CLK_ENABLE();

    GPIO_InitTypeDef GPIO_InitStruct = {0};
    GPIO_InitStruct.Pin = GPIO_PIN_9 | GPIO_PIN_10;
    GPIO_InitStruct.Mode = GPIO_MODE_AF_PP;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);
}

void GPIO_Init(void)
{
    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOC_CLK_ENABLE();

    /* PA3 = DRDY input with EXTI */
    GPIO_InitTypeDef GPIO_InitStruct = {0};
    GPIO_InitStruct.Pin = GPIO_PIN_3;
    GPIO_InitStruct.Mode = GPIO_MODE_IT_FALLING;
    GPIO_InitStruct.Pull = GPIO_NOPULL;
    HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);

    /* PC13 = LED output */
    GPIO_InitStruct.Pin = GPIO_PIN_13;
    GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(GPIOC, &GPIO_InitStruct);
    HAL_GPIO_WritePin(GPIOC, GPIO_PIN_13, GPIO_PIN_SET);
}

/* ------------------------------------------------------------------ */
/*  SPI1: 1 MHz clock, mode 0, 8-bit data                              */
/* ------------------------------------------------------------------ */
void SPI1_Init(void)
{
    hspi1.Instance = SPI1;
    hspi1.Init.Mode = SPI_MODE_MASTER;
    hspi1.Init.Direction = SPI_DIRECTION_2LINES;
    hspi1.Init.DataSize = SPI_DATASIZE_8BIT;
    hspi1.Init.CLKPolarity = SPI_POLARITY_LOW;
    hspi1.Init.CLKPhase = SPI_PHASE_1EDGE;
    hspi1.Init.NSS = SPI_NSS_SOFT;
    hspi1.Init.BaudRatePrescaler = SPI_BAUDRATEPRESCALER_64; /* 72MHz/64 = 1.125 MHz */
    hspi1.Init.FirstBit = SPI_FIRSTBIT_MSB;
    hspi1.Init.TIMode = SPI_TIMODE_DISABLE;
    hspi1.Init.CRCCalculation = SPI_CRCCALCULATION_DISABLE;
    if (HAL_SPI_Init(&hspi1) != HAL_OK) {
        Error_Handler();
    }
}

/* ------------------------------------------------------------------ */
/*  USART1: 115200-8N1                                                  */
/* ------------------------------------------------------------------ */
void UART_Init(void)
{
    huart1.Instance = USART1;
    huart1.Init.BaudRate = 115200;
    huart1.Init.WordLength = UART_WORDLENGTH_8B;
    huart1.Init.StopBits = UART_STOPBITS_1;
    huart1.Init.Parity = UART_PARITY_NONE;
    huart1.Init.Mode = UART_MODE_TX_RX;
    huart1.Init.HwFlowCtl = UART_HWCONTROL_NONE;
    huart1.Init.OverSampling = UART_OVERSAMPLING_16;
    if (HAL_UART_Init(&huart1) != HAL_OK) {
        Error_Handler();
    }
}

/* ------------------------------------------------------------------ */
/*  ADS1291 SPI helper functions                                       */
/* ------------------------------------------------------------------ */
static void SPI_CS_Low(void) {
    HAL_GPIO_WritePin(GPIOA, GPIO_PIN_4, GPIO_PIN_RESET);
}

static void SPI_CS_High(void) {
    HAL_GPIO_WritePin(GPIOA, GPIO_PIN_4, GPIO_PIN_SET);
}

static void SPI_WriteByte(uint8_t data) {
    HAL_SPI_Transmit(&hspi1, &data, 1, 100);
}

static uint8_t SPI_ReadByte(void) {
    uint8_t data = 0;
    HAL_SPI_Receive(&hspi1, &data, 1, 100);
    return data;
}

/* ------------------------------------------------------------------ */
/*  ADS1291 register operations                                        */
/* ------------------------------------------------------------------ */
static void ADS1291_WriteReg(uint8_t addr, uint8_t val) {
    SPI_CS_Low();
    SPI_WriteByte(0x40 | addr);  /* WREG command */
    SPI_WriteByte(0x00);         /* number of registers - 1 */
    SPI_WriteByte(val);
    SPI_CS_High();
}

static uint8_t ADS1291_ReadReg(uint8_t addr) {
    uint8_t val;
    SPI_CS_Low();
    SPI_WriteByte(0x20 | addr);  /* RREG command */
    SPI_WriteByte(0x00);
    val = SPI_ReadByte();
    SPI_CS_High();
    return val;
}

/* ------------------------------------------------------------------ */
/*  ADS1291 initialization                                             */
/* ------------------------------------------------------------------ */
static void ADS1291_Init(void) {
    /* Reset sequence */
    HAL_GPIO_WritePin(GPIOA, GPIO_PIN_4, GPIO_PIN_SET);
    HAL_Delay(10);
    SPI_CS_Low();
    SPI_WriteByte(0x06);  /* RESET command */
    HAL_Delay(10);
    SPI_CS_High();
    HAL_Delay(10);

    /* Configure registers */
    ADS1291_WriteReg(0x01, 0x02);  /* CONFIG1: DR = 250 SPS */
    ADS1291_WriteReg(0x02, 0x00);  /* CONFIG2: RLD off, normal mode */
    ADS1291_WriteReg(0x03, 0x00);  /* CONFIG3: external reference */
    ADS1291_WriteReg(0x04, 0x06);  /* CH1SET: gain = 6, normal electrode input */
    ADS1291_WriteReg(0x05, 0x01);  /* CH2SET: power down */

    /* Start continuous conversion */
    SPI_CS_Low();
    SPI_WriteByte(0x08);  /* START command */
    SPI_CS_High();
    HAL_Delay(10);
}

/* ------------------------------------------------------------------ */
/*  Read 24-bit sample from ADS1291                                    */
/* ------------------------------------------------------------------ */
static int32_t ADS1291_ReadSample(void) {
    uint8_t data[3];
    int32_t sample = 0;

    SPI_CS_Low();
    SPI_WriteByte(0x11);  /* RDATAC command */
    data[0] = SPI_ReadByte();
    data[1] = SPI_ReadByte();
    data[2] = SPI_ReadByte();
    SPI_CS_High();

    /* Convert 24-bit two's complement to 32-bit signed */
    sample = ((int32_t)data[0] << 16) | ((int32_t)data[1] << 8) | data[2];
    if (sample & 0x800000) {
        sample |= 0xFF000000;  /* sign extend */
    }

    return sample;
}

/* ------------------------------------------------------------------ */
/*  EXTI interrupt handler for DRDY (PA3)                              */
/* ------------------------------------------------------------------ */
void EXTI3_IRQHandler(void) {
    HAL_GPIO_EXTI_IRQHandler(GPIO_PIN_3);
}

void HAL_GPIO_EXTI_Callback(uint16_t GPIO_Pin) {
    if (GPIO_Pin == GPIO_PIN_3) {
        g_drdy_flag = 1;
    }
}

/* ------------------------------------------------------------------ */
/*  Ring buffer helpers                                                */
/* ------------------------------------------------------------------ */
static void ring_push(int32_t v) {
    g_ring[g_ring_head] = v;
    g_ring_head = (g_ring_head + 1U) & 0xFFU;
    if (g_ring_count < 256U) {
        g_ring_count++;
    } else {
        g_ring_tail = g_ring_head;
    }
}

static uint16_t ring_pop_batch(int32_t *out, uint16_t max) {
    __disable_irq();
    uint16_t n = (g_ring_count < max) ? g_ring_count : max;
    for (uint16_t i = 0; i < n; i++) {
        out[i] = g_ring[g_ring_tail];
        g_ring_tail = (g_ring_tail + 1U) & 0xFFU;
    }
    g_ring_count -= n;
    __enable_irq();
    return n;
}

/* ------------------------------------------------------------------ */
/*  Frame transmit                                                     */
/* ------------------------------------------------------------------ */
static uint8_t crc8(const uint8_t *data, uint16_t len) {
    uint8_t crc = 0x00;
    for (uint16_t i = 0; i < len; i++) {
        crc ^= data[i];
        for (uint8_t b = 0; b < 8; b++) {
            if (crc & 0x80) {
                crc = (uint8_t)((crc << 1) ^ 0x07);
            } else {
                crc <<= 1;
            }
        }
    }
    return crc;
}

static void send_frame(void) {
    static int32_t samples[FRAME_MAX_SAMPLES];
    uint16_t n = ring_pop_batch(samples, FRAME_MAX_SAMPLES);
    if (n == 0U) {
        return;
    }

    uint8_t pkt[6 + FRAME_MAX_SAMPLES * 4 + 1];  /* 32-bit samples */
    uint16_t idx = 0U;

    pkt[idx++] = FRAME_HEADER0;
    pkt[idx++] = FRAME_HEADER1;
    pkt[idx++] = (uint8_t)(g_seq & 0xFF);
    pkt[idx++] = (uint8_t)((g_seq >> 8) & 0xFF);
    pkt[idx++] = (uint8_t)(n & 0xFF);
    pkt[idx++] = (uint8_t)((n >> 8) & 0xFF);
    memcpy(&pkt[idx], samples, n * 4U);
    idx += (uint16_t)(n * 4U);
    pkt[idx] = crc8(pkt, idx);
    idx++;

    HAL_UART_Transmit(&huart1, pkt, idx, 100);
    g_seq++;
}

/* ------------------------------------------------------------------ */
/*  LED toggle                                                         */
/* ------------------------------------------------------------------ */
static void led_toggle(void) {
    HAL_GPIO_TogglePin(GPIOC, GPIO_PIN_13);
}

/* ------------------------------------------------------------------ */
/*  Error handler                                                      */
/* ------------------------------------------------------------------ */
void Error_Handler(void) {
    __disable_irq();
    while (1) {
        HAL_GPIO_TogglePin(GPIOC, GPIO_PIN_13);
        for (volatile uint32_t i = 0; i < 100000U; i++) {
            __NOP();
        }
    }
}

/* ------------------------------------------------------------------ */
/*  SysTick handler                                                    */
/* ------------------------------------------------------------------ */
void SysTick_Handler(void) {
    HAL_IncTick();
}

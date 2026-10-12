/*
 * EEG Waveform Monitor - STM32F103C8T6 firmware
 *
 * Sampling pipeline:
 *   TIM3 update event (250 Hz) -> ADC1 software start -> EOC IRQ
 *   -> samples pushed to a ring buffer -> main loop flushes in framed packets
 *   -> USART1 TX @ 115200 baud to USB-TTL adapter
 *
 * Packet format (binary, little-endian):
 *   [0xAA][0x55][seq:u16][count:u16][samples:count * i16][crc8:u8]
 *
 * Wiring:
 *   PA0  <- AD8232 OUTPUT
 *   PA9  -> USB-TTL RXD  (USART1 TX)
 *   PA10 <- USB-TTL TXD  (USART1 RX, optional)
 *   PC13 -> onboard LED  (status blink)
 */

#include "stm32f1xx_hal.h"
#include <string.h>

/* ------------------------------------------------------------------ */
/*  Handles and globals                                                */
/* ------------------------------------------------------------------ */
ADC_HandleTypeDef  hadc1;
UART_HandleTypeDef huart1;
TIM_HandleTypeDef  htim3;

#define SAMPLE_RATE_HZ      250U
#define ADC_FULL_SCALE      4096U          /* 12-bit ADC                  */
#define ADC_MID             2048U          /* mid-scale offset            */
#define FRAME_MAX_SAMPLES   16U            /* samples per packet          */
#define FRAME_HEADER0       0xAAU
#define FRAME_HEADER1       0x55U

static volatile uint16_t g_seq         = 0;
static volatile int16_t  g_ring[256];      /* ring buffer of int16 samples */
static volatile uint16_t g_ring_head   = 0;
static volatile uint16_t g_ring_tail   = 0;
static volatile uint16_t g_ring_count  = 0;
static volatile uint16_t g_latest_raw  = 0;
static volatile uint8_t  g_adc_ready   = 0;

/* ------------------------------------------------------------------ */
/*  Forward declarations                                               */
/* ------------------------------------------------------------------ */
void SystemClock_Config(void);
void ADC_Init(void);
void UART_Init(void);
void TIM3_Init(void);
void LED_Init(void);
void Error_Handler(void);
void HAL_ADC_MspInit(ADC_HandleTypeDef *hadc);
void HAL_UART_MspInit(UART_HandleTypeDef *huart);
static uint8_t crc8(const uint8_t *data, uint16_t len);
static void ring_push(int16_t v);
static uint16_t ring_pop_batch(int16_t *out, uint16_t max);
static void send_frame(void);
static void led_toggle(void);

/* ------------------------------------------------------------------ */
/*  Main                                                              */
/* ------------------------------------------------------------------ */
int main(void)
{
    HAL_Init();
    SystemClock_Config();

    LED_Init();
    ADC_Init();
    UART_Init();
    TIM3_Init();

    /* Self-calibration of the ADC (improves offset/linearity). */
    if (HAL_ADCEx_Calibration_Start(&hadc1) != HAL_OK) {
        Error_Handler();
    }

    /* Start ADC with EOC interrupt; TIM3 TRGO will trigger conversions. */
    if (HAL_ADC_Start_IT(&hadc1) != HAL_OK) {
        Error_Handler();
    }
    if (HAL_TIM_Base_Start(&htim3) != HAL_OK) {
        Error_Handler();
    }

    while (1) {
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
    RCC_OscInitStruct.HSEState       = RCC_HSE_ON;
    RCC_OscInitStruct.PLL.PLLState   = RCC_PLL_ON;
    RCC_OscInitStruct.PLL.PLLSource  = RCC_PLLSOURCE_HSE;
    RCC_OscInitStruct.PLL.PLLMUL     = RCC_PLL_MUL9;
    if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK) {
        Error_Handler();
    }

    RCC_ClkInitStruct.ClockType      = RCC_CLOCKTYPE_HCLK | RCC_CLOCKTYPE_SYSCLK |
                                       RCC_CLOCKTYPE_PCLK1 | RCC_CLOCKTYPE_PCLK2;
    RCC_ClkInitStruct.SYSCLKSource   = RCC_SYSCLKSOURCE_PLLCLK;
    RCC_ClkInitStruct.AHBCLKDivider  = RCC_SYSCLK_DIV1;
    RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV2;   /* APB1 = 36 MHz */
    RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;   /* APB2 = 72 MHz */
    if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_2) != HAL_OK) {
        Error_Handler();
    }
}

/* ------------------------------------------------------------------ */
/*  GPIO / peripheral MSP init                                         */
/* ------------------------------------------------------------------ */
void HAL_ADC_MspInit(ADC_HandleTypeDef *hadc)
{
    if (hadc->Instance != ADC1) {
        return;
    }

    __HAL_RCC_ADC1_CLK_ENABLE();
    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_DMA1_CLK_ENABLE();   /* kept for future DMA mode */

    GPIO_InitTypeDef GPIO_InitStruct = {0};
    GPIO_InitStruct.Pin  = GPIO_PIN_0;            /* PA0 = ADC1_IN0 */
    GPIO_InitStruct.Mode = GPIO_MODE_ANALOG;
    GPIO_InitStruct.Pull = GPIO_NOPULL;
    HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);

    /* ADC clock = PCLK2/2 = 36 MHz (set by ADCPRE in CFGR). */
    RCC_PeriphCLKInitTypeDef PeriphClkInit = {0};
    PeriphClkInit.PeriphClockSelection = RCC_PERIPHCLK_ADC;
    PeriphClkInit.AdcClockSelection     = RCC_ADCPCLK2_DIV2;
    HAL_RCCEx_PeriphCLKConfig(&PeriphClkInit);
}

void HAL_UART_MspInit(UART_HandleTypeDef *huart)
{
    if (huart->Instance != USART1) {
        return;
    }

    __HAL_RCC_USART1_CLK_ENABLE();
    __HAL_RCC_GPIOA_CLK_ENABLE();

    GPIO_InitTypeDef GPIO_InitStruct = {0};
    GPIO_InitStruct.Pin   = GPIO_PIN_9 | GPIO_PIN_10;
    GPIO_InitStruct.Mode  = GPIO_MODE_AF_PP;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);
}

/* ------------------------------------------------------------------ */
/*  ADC: 12-bit, software-start, single channel, EOC interrupt        */
/* ------------------------------------------------------------------ */
void ADC_Init(void)
{
    hadc1.Instance                   = ADC1;
    hadc1.Init.ScanConvMode          = ADC_SCAN_DISABLE;
    hadc1.Init.ContinuousConvMode    = DISABLE;        /* TIM3 triggers */
    hadc1.Init.DiscontinuousConvMode = DISABLE;
    hadc1.Init.ExternalTrigConv      = ADC_SOFTWARE_START;
    hadc1.Init.DataAlign             = ADC_DATAALIGN_RIGHT;
    hadc1.Init.NbrOfConversion       = 1;
    if (HAL_ADC_Init(&hadc1) != HAL_OK) {
        Error_Handler();
    }

    ADC_ChannelConfTypeDef sConfig = {0};
    sConfig.Channel       = ADC_CHANNEL_0;
    sConfig.Rank          = 1;
    sConfig.SamplingTime  = ADC_SAMPLETIME_55CYCLES_5;   /* ~1.5 us @ 36 MHz */
    if (HAL_ADC_ConfigChannel(&hadc1, &sConfig) != HAL_OK) {
        Error_Handler();
    }
}

/* ------------------------------------------------------------------ */
/*  USART1: 115200-8N1                                                  */
/* ------------------------------------------------------------------ */
void UART_Init(void)
{
    huart1.Instance        = USART1;
    huart1.Init.BaudRate   = 115200;
    huart1.Init.WordLength = UART_WORDLENGTH_8B;
    huart1.Init.StopBits   = UART_STOPBITS_1;
    huart1.Init.Parity     = UART_PARITY_NONE;
    huart1.Init.Mode       = UART_MODE_TX_RX;
    huart1.Init.HwFlowCtl  = UART_HWCONTROL_NONE;
    huart1.Init.OverSampling = UART_OVERSAMPLING_16;
    if (HAL_UART_Init(&huart1) != HAL_OK) {
        Error_Handler();
    }
}

/* ------------------------------------------------------------------ */
/*  TIM3: 250 Hz update event (TRGO) - drives ADC conversions          */
/*  APB1 timer clock = 72 MHz, PSC = 7199 -> 10 kHz, ARR = 39 -> 250 Hz*/
/* ------------------------------------------------------------------ */
void TIM3_Init(void)
{
    __HAL_RCC_TIM3_CLK_ENABLE();

    htim3.Instance               = TIM3;
    htim3.Init.Prescaler         = 7199U;
    htim3.Init.CounterMode       = TIM_COUNTERMODE_UP;
    htim3.Init.Period            = 39U;
    htim3.Init.ClockDivision     = TIM_CLOCKDIVISION_DIV1;
    htim3.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_ENABLE;
    if (HAL_TIM_Base_Init(&htim3) != HAL_OK) {
        Error_Handler();
    }

    TIM_MasterConfigTypeDef sMaster = {0};
    sMaster.MasterOutputTrigger = TIM_TRGO_UPDATE;
    sMaster.MasterSlaveMode    = TIM_MASTERSLAVEMODE_DISABLE;
    if (HAL_TIMEx_MasterConfigSynchronization(&htim3, &sMaster) != HAL_OK) {
        Error_Handler();
    }
}

/* ------------------------------------------------------------------ */
/*  Onboard LED on PC13 (active-low on Blue Pill)                      */
/* ------------------------------------------------------------------ */
void LED_Init(void)
{
    __HAL_RCC_GPIOC_CLK_ENABLE();

    GPIO_InitTypeDef GPIO_InitStruct = {0};
    GPIO_InitStruct.Pin   = GPIO_PIN_13;
    GPIO_InitStruct.Mode  = GPIO_MODE_OUTPUT_PP;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(GPIOC, &GPIO_InitStruct);

    HAL_GPIO_WritePin(GPIOC, GPIO_PIN_13, GPIO_PIN_SET);  /* LED off */
}

static void led_toggle(void)
{
    HAL_GPIO_TogglePin(GPIOC, GPIO_PIN_13);
}

/* ------------------------------------------------------------------ */
/*  Ring buffer helpers (single producer = ADC IRQ, single consumer   */
/*  = main loop). Lock-free for the SPSC case.                         */
/* ------------------------------------------------------------------ */
static void ring_push(int16_t v)
{
    g_ring[g_ring_head] = v;
    g_ring_head = (g_ring_head + 1U) & 0xFFU;            /* mod 256 */
    if (g_ring_count < 256U) {
        g_ring_count++;
    } else {
        /* Overwrite oldest: advance tail to match head. */
        g_ring_tail = g_ring_head;
    }
}

static uint16_t ring_pop_batch(int16_t *out, uint16_t max)
{
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
static uint8_t crc8(const uint8_t *data, uint16_t len)
{
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

static void send_frame(void)
{
    static int16_t samples[FRAME_MAX_SAMPLES];
    uint16_t n = ring_pop_batch(samples, FRAME_MAX_SAMPLES);
    if (n == 0U) {
        return;
    }

    uint8_t pkt[6 + FRAME_MAX_SAMPLES * 2 + 1];
    uint16_t idx = 0U;

    pkt[idx++] = FRAME_HEADER0;
    pkt[idx++] = FRAME_HEADER1;
    pkt[idx++] = (uint8_t)(g_seq & 0xFF);
    pkt[idx++] = (uint8_t)((g_seq >> 8) & 0xFF);
    pkt[idx++] = (uint8_t)(n & 0xFF);
    pkt[idx++] = (uint8_t)((n >> 8) & 0xFF);
    memcpy(&pkt[idx], samples, n * 2U);
    idx += (uint16_t)(n * 2U);
    pkt[idx] = crc8(pkt, idx);
    idx++;

    HAL_UART_Transmit(&huart1, pkt, idx, 100);
    g_seq++;
}

/* ------------------------------------------------------------------ */
/*  ADC end-of-conversion callback                                     */
/* ------------------------------------------------------------------ */
void HAL_ADC_ConvCpltCallback(ADC_HandleTypeDef *hadc)
{
    if (hadc->Instance != ADC1) {
        return;
    }

    uint16_t raw = HAL_ADC_GetValue(&hadc1);
    g_latest_raw = raw;

    /* Center around zero and scale to int16 range.
     * raw is 0..4095, subtract mid -> -2048..2047, scale x8 to ~-16384..16383.
     */
    int16_t v = (int16_t)(((int32_t)raw - (int32_t)ADC_MID) * 8);
    ring_push(v);

    /* Re-arm ADC for the next TIM3-triggered conversion. */
    HAL_ADC_Start_IT(&hadc1);
}

/* ------------------------------------------------------------------ */
/*  Error handler: blink LED forever at ~5 Hz                          */
/* ------------------------------------------------------------------ */
void Error_Handler(void)
{
    __disable_irq();
    while (1) {
        HAL_GPIO_TogglePin(GPIOC, GPIO_PIN_13);
        /* Rough delay at 72 MHz: ~100 k cycles. */
        for (volatile uint32_t i = 0; i < 100000U; i++) {
            __NOP();
        }
    }
}

/* ------------------------------------------------------------------ */
/*  Required HAL tick (SysTick) - provided by HAL, override optional   */
/* ------------------------------------------------------------------ */
void SysTick_Handler(void)
{
    HAL_IncTick();
}

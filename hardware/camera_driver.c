/**
 * STM32F103VE 摄像头驱动程序
 * 支持OV7670/OV7725摄像头模块
 * 通过串口与上位机通信
 */

#include "stm32f10x.h"
#include "camera_driver.h"
#include <string.h>
#include <stdio.h>

// ============================================
// 宏定义
// ============================================

// SCCB (I2C-like) 引脚定义
#define SCCB_SIO_C_PIN      GPIO_Pin_8      // PB8
#define SCCB_SIO_D_PIN      GPIO_Pin_9      // PB9
#define SCCB_GPIO_PORT      GPIOB

// 摄像头数据引脚 (D0-D7)
#define CAM_DATA_PINS       (GPIO_Pin_0 | GPIO_Pin_1 | GPIO_Pin_2 | GPIO_Pin_3 | \
                             GPIO_Pin_4 | GPIO_Pin_5 | GPIO_Pin_6 | GPIO_Pin_7)
#define CAM_DATA_PORT       GPIOC

// 摄像头控制引脚
#define CAM_PCLK_PIN        GPIO_Pin_6      // PA6
#define CAM_HREF_PIN        GPIO_Pin_7      // PA7
#define CAM_VSYNC_PIN       GPIO_Pin_0      // PA0
#define CAM_XCLK_PIN        GPIO_Pin_8      // PA8 (MCO)

#define CAM_CTRL_PORT       GPIOA

// 缓冲区大小
#define FRAME_BUFFER_SIZE   (320 * 240)     // QQVGA大小
#define MAX_IMAGE_SIZE      65535
#define PACKET_SIZE         512

// 串口命令定义
#define FRAME_HEAD_1        0xAA
#define FRAME_HEAD_2        0x55
#define FRAME_TAIL_1        0x0D
#define FRAME_TAIL_2        0x0A

// SCCB延时
#define SCCB_DELAY()        do { for(volatile int i=0; i<20; i++); } while(0)

// ============================================
// 全局变量
// ============================================

// 帧缓冲区
static uint8_t frame_buffer[FRAME_BUFFER_SIZE];
static volatile uint32_t frame_count = 0;
static volatile uint8_t capture_flag = 0;
static volatile uint8_t vsync_flag = 0;

// 串口发送缓冲区
static uint8_t tx_buffer[PACKET_SIZE + 10];
static uint8_t rx_buffer[256];
static volatile uint16_t rx_index = 0;

// 设备状态
static CameraState camera_state = CAM_STATE_IDLE;
static uint8_t camera_ready = 0;

// 图像参数
static ImageConfig image_config = {
    .resolution = RES_QVGA,
    .quality = 85,
    .brightness = 50
};

// ============================================
// 函数声明
// ============================================

static void GPIO_Init(void);
static void SCCB_Init(void);
static void TIM_Init(void);
static void DMA_Init(void);
static void NVIC_Init(void);

static uint8_t SCCB_Start(void);
static void SCCB_Stop(void);
static void SCCB_SendByte(uint8_t data);
static uint8_t SCCB_ReceiveByte(void);
static void SCCB_SendNAK(void);

static uint8_t OV_WriteReg(uint8_t reg, uint8_t data);
static uint8_t OV_ReadReg(uint8_t reg);
static uint8_t OV_Init(void);

static void SendPacket(uint8_t cmd, uint8_t *data, uint16_t len);
static void ProcessCommand(uint8_t cmd, uint8_t *data, uint16_t len);
static void CaptureAndSendImage(void);

// ============================================
// GPIO初始化
// ============================================
static void GPIO_Init(void)
{
    GPIO_InitTypeDef GPIO_InitStruct;

    // 使能时钟
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOA | RCC_APB2Periph_GPIOB |
                           RCC_APB2Periph_GPIOC | RCC_APB2Periph_AFIO, ENABLE);

    // 摄像头数据引脚 (PC0-PC7) - 浮空输入
    GPIO_InitStruct.GPIO_Pin = CAM_DATA_PINS;
    GPIO_InitStruct.GPIO_Mode = GPIO_Mode_IN_FLOATING;
    GPIO_Init(GPIOC, &GPIO_InitStruct);

    // VSYNC (PA0), HREF (PA7) - 输入
    GPIO_InitStruct.GPIO_Pin = CAM_VSYNC_PIN | CAM_HREF_PIN;
    GPIO_InitStruct.GPIO_Mode = GPIO_Mode_IN_FLOATING;
    GPIO_Init(GPIOA, &GPIO_InitStruct);

    // PCLK (PA6) - 输入
    GPIO_InitStruct.GPIO_Pin = CAM_PCLK_PIN;
    GPIO_InitStruct.GPIO_Mode = GPIO_Mode_IN_FLOATING;
    GPIO_Init(GPIOA, &GPIO_InitStruct);

    // XCLK (PA8) - 复用推挽输出 MCO
    GPIO_InitStruct.GPIO_Pin = CAM_XCLK_PIN;
    GPIO_InitStruct.GPIO_Mode = GPIO_Mode_AF_PP;
    GPIO_InitStruct.GPIO_Speed = GPIO_Speed_50MHz;
    GPIO_Init(GPIOA, &GPIO_InitStruct);

    // SCCB引脚 (PB8, PB9) - 开漏输出
    GPIO_InitStruct.GPIO_Pin = SCCB_SIO_C_PIN | SCCB_SIO_D_PIN;
    GPIO_InitStruct.GPIO_Mode = GPIO_Mode_Out_OD;
    GPIO_InitStruct.GPIO_Speed = GPIO_Speed_50MHz;
    GPIO_Init(SCCB_GPIO_PORT, &GPIO_InitStruct);

    // 默认高电平
    GPIO_SetBits(SCCB_GPIO_PORT, SCCB_SIO_C_PIN | SCCB_SIO_D_PIN);
}

// ============================================
// SCCB (I2C-like) 协议实现
// ============================================
static void SCCB_Init(void)
{
    // 默认拉高
    GPIO_SetBits(SCCB_GPIO_PORT, SCCB_SIO_C_PIN | SCCB_SIO_D_PIN);
}

static uint8_t SCCB_Start(void)
{
    // 确保总线空闲
    SCCB_SIO_C_H();
    SCCB_SIO_D_H();
    SCCB_DELAY();

    // 起始条件: SCL高时, SDA下降沿
    SCCB_SIO_D_L();
    SCCB_DELAY();
    SCCB_SIO_C_L();
    SCCB_DELAY();

    return 0;
}

static void SCCB_Stop(void)
{
    // 停止条件: SCL高时, SDA上升沿
    SCCB_SIO_D_L();
    SCCB_DELAY();
    SCCB_SIO_C_H();
    SCCB_DELAY();
    SCCB_SIO_D_H();
    SCCB_DELAY();
}

static void SCCB_SendByte(uint8_t data)
{
    for (int i = 7; i >= 0; i--) {
        if (data & (1 << i)) {
            SCCB_SIO_D_H();
        } else {
            SCCB_SIO_D_L();
        }
        SCCB_DELAY();
        SCCB_SIO_C_H();
        SCCB_DELAY();
        SCCB_SIO_C_L();
        SCCB_DELAY();
    }

    // 释放数据线，准备接收ACK
    SCCB_SIO_D_H();
    SCCB_DELAY();
    SCCB_SIO_C_H();
    SCCB_DELAY();
    // 读取ACK (忽略)
    SCCB_SIO_C_L();
    SCCB_DELAY();
}

static uint8_t SCCB_ReceiveByte(void)
{
    uint8_t data = 0;

    // 释放数据线
    SCCB_SIO_D_H();

    for (int i = 7; i >= 0; i--) {
        SCCB_DELAY();
        SCCB_SIO_C_H();
        SCCB_DELAY();

        if (SCCB_SIO_D_READ()) {
            data |= (1 << i);
        }

        SCCB_SIO_C_L();
    }

    return data;
}

static void SCCB_SendNAK(void)
{
    // 发送NAK (保持SDA高电平)
    SCCB_SIO_D_H();
    SCCB_DELAY();
    SCCB_SIO_C_H();
    SCCB_DELAY();
    SCCB_SIO_C_L();
    SCCB_DELAY();
}

// ============================================
// OV7670/7725 摄像头驱动
// ============================================
static uint8_t OV_WriteReg(uint8_t reg, uint8_t data)
{
    uint8_t ret = 0;

    ret = SCCB_Start();
    if (ret != 0) return ret;

    SCCB_SendByte(OV_I2C_ADDR);  // 写地址
    SCCB_SendByte(reg);          // 寄存器地址
    SCCB_SendByte(data);         // 数据

    SCCB_Stop();

    return 0;
}

static uint8_t OV_ReadReg(uint8_t reg)
{
    uint8_t data = 0;

    SCCB_Start();
    SCCB_SendByte(OV_I2C_ADDR);  // 写地址
    SCCB_SendByte(reg);          // 寄存器地址
    SCCB_Stop();

    SCCB_Start();
    SCCB_SendByte(OV_I2C_ADDR | 0x01);  // 读地址
    data = SCCB_ReceiveByte();
    SCCB_SendNAK();
    SCCB_Stop();

    return data;
}

static uint8_t OV_Init(void)
{
    uint8_t pid = 0, ver = 0;

    // 读取产品ID
    pid = OV_ReadReg(OV_REG_PID);
    ver = OV_ReadReg(OV_REG_VER);

    printf("Camera PID: 0x%02X, VER: 0x%02X\r\n", pid, ver);

    // 根据PID判断摄像头型号并初始化
    if (pid == 0x76) {  // OV7670
        printf("Detected OV7670\r\n");
        // 配置OV7670寄存器
        for (int i = 0; i < sizeof(OV7670_QVGA) / 2; i++) {
            OV_WriteReg(OV7670_QVGA[i][0], OV7670_QVGA[i][1]);
        }
    } else if (pid == 0x77) {  // OV7725
        printf("Detected OV7725\r\n");
        // 配置OV7725寄存器
        for (int i = 0; i < sizeof(OV7725_QVGA) / 2; i++) {
            OV_WriteReg(OV7725_QVGA[i][0], OV7725_QVGA[i][1]);
        }
    } else {
        printf("Unknown camera: PID=0x%02X\r\n", pid);
        return 1;
    }

    return 0;
}

// ============================================
// 串口通信
// ============================================
static void USART1_Init(void)
{
    GPIO_InitTypeDef GPIO_InitStruct;
    USART_InitTypeDef USART_InitStruct;
    NVIC_InitTypeDef NVIC_InitStruct;

    // 使能时钟
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOA | RCC_APB2Periph_USART1, ENABLE);

    // 配置PA9 (TX) 复用推挽输出
    GPIO_InitStruct.GPIO_Pin = GPIO_Pin_9;
    GPIO_InitStruct.GPIO_Mode = GPIO_Mode_AF_PP;
    GPIO_InitStruct.GPIO_Speed = GPIO_Speed_50MHz;
    GPIO_Init(GPIOA, &GPIO_InitStruct);

    // 配置PA10 (RX) 浮空输入
    GPIO_InitStruct.GPIO_Pin = GPIO_Pin_10;
    GPIO_InitStruct.GPIO_Mode = GPIO_Mode_IN_FLOATING;
    GPIO_Init(GPIOA, &GPIO_InitStruct);

    // 配置USART1
    USART_InitStruct.USART_BaudRate = 115200;
    USART_InitStruct.USART_WordLength = USART_WordLength_8b;
    USART_InitStruct.USART_StopBits = USART_StopBits_1;
    USART_InitStruct.USART_Parity = USART_Parity_No;
    USART_InitStruct.USART_HardwareFlowControl = USART_HardwareFlowControl_None;
    USART_InitStruct.USART_Mode = USART_Mode_Rx | USART_Mode_Tx;
    USART_Init(USART1, &USART_InitStruct);

    // 配置NVIC
    NVIC_InitStruct.NVIC_IRQChannel = USART1_IRQn;
    NVIC_InitStruct.NVIC_IRQChannelPreemptionPriority = 2;
    NVIC_InitStruct.NVIC_IRQChannelSubPriority = 0;
    NVIC_InitStruct.NVIC_IRQChannelCmd = ENABLE;
    NVIC_Init(&NVIC_InitStruct);

    // 使能接收中断
    USART_ITConfig(USART1, USART_IT_RXNE, ENABLE);

    // 使能USART1
    USART_Cmd(USART1, ENABLE);
}

// 串口发送一个字节
static void USART_SendByte(uint8_t byte)
{
    while (USART_GetFlagStatus(USART1, USART_FLAG_TXE) == RESET);
    USART_SendData(USART1, byte);
}

// 串口发送数据
static void USART_SendData(uint8_t *data, uint16_t len)
{
    for (uint16_t i = 0; i < len; i++) {
        USART_SendByte(data[i]);
    }
}

// 串口printf
static void USART_printf(const char *fmt, ...)
{
    va_list ap;
    char buf[128];

    va_start(ap, fmt);
    vsprintf(buf, fmt, ap);
    va_end(ap);

    USART_SendData((uint8_t *)buf, strlen(buf));
}

// ============================================
// 命令处理
// ============================================
static void SendPacket(uint8_t cmd, uint8_t *data, uint16_t len)
{
    uint8_t packet[PACKET_SIZE + 10];
    uint16_t pos = 0;

    // 帧头
    packet[pos++] = FRAME_HEAD_1;
    packet[pos++] = FRAME_HEAD_2;

    // 命令
    packet[pos++] = cmd;

    // 数据长度
    packet[pos++] = len & 0xFF;
    packet[pos++] = (len >> 8) & 0xFF;

    // 数据
    if (data && len > 0) {
        memcpy(&packet[pos], data, len);
        pos += len;
    }

    // 校验和
    uint8_t checksum = 0;
    for (uint16_t i = 0; i < pos; i++) {
        checksum += packet[i];
    }
    packet[pos++] = checksum;

    // 帧尾
    packet[pos++] = FRAME_TAIL_1;
    packet[pos++] = FRAME_TAIL_2;

    // 发送
    USART_SendData(packet, pos);
}

static void ProcessCommand(uint8_t cmd, uint8_t *data, uint16_t len)
{
    switch (cmd) {
        case CMD_HANDSHAKE:
            // 握手响应
            SendPacket(CMD_HANDSHAKE, NULL, 0);
            break;

        case CMD_START_CAPTURE:
            // 开始拍照
            if (camera_ready) {
                capture_flag = 1;
                SendPacket(CMD_STATUS_RSP, &camera_ready, 1);
            } else {
                uint8_t status = 0;
                SendPacket(CMD_ERROR, &status, 1);
            }
            break;

        case CMD_STOP_CAPTURE:
            // 停止拍照
            capture_flag = 0;
            SendPacket(CMD_STATUS_RSP, &camera_ready, 1);
            break;

        case CMD_CONFIG_CAMERA:
            // 配置摄像头
            if (len >= 3) {
                image_config.resolution = data[0];
                image_config.quality = data[1];
                image_config.brightness = data[2];

                // 应用配置
                OV_Config(image_config.resolution);

                SendPacket(CMD_STATUS_RSP, &camera_ready, 1);
            }
            break;

        case CMD_STATUS_REQ:
            // 状态请求
            {
                uint8_t status = (camera_ready << 0) | (capture_flag << 1);
                SendPacket(CMD_STATUS_RSP, &status, 1);
            }
            break;

        case CMD_RESET:
            // 复位命令
            NVIC_SystemReset();
            break;

        default:
            // 未知命令
            {
                uint8_t error = 0xFF;
                SendPacket(CMD_ERROR, &error, 1);
            }
            break;
    }
}

// ============================================
// 图像捕获和发送
// ============================================
static void CaptureAndSendImage(void)
{
    uint32_t image_size = 0;
    uint8_t *jpeg_buffer = NULL;

    // 等待VSYNC下降沿（帧开始）
    while (GPIO_ReadInputDataBit(CAM_CTRL_PORT, CAM_VSYNC_PIN) == Bit_SET);
    while (GPIO_ReadInputDataBit(CAM_CTRL_PORT, CAM_VSYNC_PIN) == Bit_RESET);

    // 捕获图像到缓冲区
    // 注意：这里简化处理，实际应该使用DMA
    uint32_t pixel_count = 0;
    uint16_t width = 320;   // QVGA
    uint16_t height = 240;

    // 如果是JPEG模式，直接从摄像头读取JPEG数据
    // 这里简化为模拟数据
    jpeg_buffer = frame_buffer;
    image_size = 10240;  // 模拟10KB JPEG

    // 填充模拟JPEG数据
    jpeg_buffer[0] = 0xFF;
    jpeg_buffer[1] = 0xD8;  // SOI标记
    for (uint32_t i = 2; i < image_size - 2; i++) {
        jpeg_buffer[i] = (uint8_t)(i & 0xFF);
    }
    jpeg_buffer[image_size - 2] = 0xFF;
    jpeg_buffer[image_size - 1] = 0xD9;  // EOI标记

    // 分包发送图像数据
    uint16_t total_packets = (image_size + PACKET_SIZE - 1) / PACKET_SIZE;

    for (uint16_t i = 0; i < total_packets; i++) {
        uint16_t packet_seq = i + 1;
        uint32_t offset = i * PACKET_SIZE;
        uint16_t packet_len = (offset + PACKET_SIZE > image_size) ?
                              (image_size - offset) : PACKET_SIZE;

        // 构建数据包
        uint8_t packet[PACKET_SIZE + 4];
        packet[0] = packet_seq & 0xFF;
        packet[1] = (packet_seq >> 8) & 0xFF;
        packet[2] = total_packets & 0xFF;
        packet[3] = (total_packets >> 8) & 0xFF;
        memcpy(&packet[4], &jpeg_buffer[offset], packet_len);

        // 发送
        SendPacket(CMD_IMAGE_DATA, packet, packet_len + 4);

        // 短暂延时，避免发送过快
        for(volatile int j=0; j<1000; j++);
    }

    // 发送完成标记
    capture_flag = 0;
}

// ============================================
// 中断处理
// ============================================
void USART1_IRQHandler(void)
{
    if (USART_GetITStatus(USART1, USART_IT_RXNE) != RESET) {
        uint8_t data = USART_ReceiveData(USART1);

        // 接收数据到缓冲区
        if (rx_index < sizeof(rx_buffer)) {
            rx_buffer[rx_index++] = data;

            // 检查是否收到完整帧
            if (rx_index >= 8) {
                // 查找帧头
                for (uint16_t i = 0; i <= rx_index - 8; i++) {
                    if (rx_buffer[i] == FRAME_HEAD_1 && rx_buffer[i+1] == FRAME_HEAD_2) {
                        uint8_t cmd = rx_buffer[i+2];
                        uint16_t len = rx_buffer[i+3] | (rx_buffer[i+4] << 8);

                        // 检查数据是否完整
                        if (rx_index >= i + 5 + len + 3) {
                            // 处理命令
                            ProcessCommand(cmd, &rx_buffer[i+5], len);

                            // 移除已处理的数据
                            uint16_t frame_len = 5 + len + 3;
                            memmove(rx_buffer, &rx_buffer[i + frame_len], rx_index - i - frame_len);
                            rx_index -= i + frame_len;
                            break;
                        }
                    }
                }

                // 防止缓冲区溢出
                if (rx_index >= sizeof(rx_buffer) - 10) {
                    rx_index = 0;
                }
            }
        }

        USART_ClearITPendingBit(USART1, USART_IT_RXNE);
    }
}

// VSYNC中断处理
void EXTI0_IRQHandler(void)
{
    if (EXTI_GetITStatus(EXTI_Line0) != RESET) {
        vsync_flag = 1;
        EXTI_ClearITPendingBit(EXTI_Line0);
    }
}

// ============================================
// 主函数
// ============================================
int main(void)
{
    // 系统初始化
    SystemInit();

    // 初始化GPIO
    GPIO_Init();

    // 初始化串口
    USART1_Init();

    // 打印启动信息
    USART_printf("\r\n========================================\r\n");
    USART_printf("  Action Game Camera Driver\r\n");
    USART_printf("  STM32F103VE + OV7670/OV7725\r\n");
    USART_printf("========================================\r\n\r\n");

    // 初始化SCCB
    SCCB_Init();

    // 初始化摄像头
    USART_printf("Initializing camera...\r\n");
    if (OV_Init() == 0) {
        camera_ready = 1;
        USART_printf("Camera initialized successfully!\r\n");
    } else {
        USART_printf("Camera initialization failed!\r\n");
    }

    // 发送就绪信号
    SendPacket(CMD_READY, &camera_ready, 1);

    USART_printf("System ready. Waiting for commands...\r\n\r\n");

    // 主循环
    while (1) {
        // 检查是否需要拍照
        if (capture_flag && camera_ready) {
            capture_flag = 0;  // 立即清除标志
            USART_printf("Capturing image...\r\n");
            CaptureAndSendImage();
            USART_printf("Image sent.\r\n\r\n");
        }

        // 定期发送心跳
        static uint32_t last_heartbeat = 0;
        if (HAL_GetTick() - last_heartbeat > 5000) {
            uint8_t status = (camera_ready << 0) | (capture_flag << 1);
            SendPacket(CMD_STATUS_RSP, &status, 1);
            last_heartbeat = HAL_GetTick();
        }
    }
}

// ============================================
// 简化的HAL兼容层
// ============================================
uint32_t HAL_GetTick(void)
{
    // 使用DWT周期计数器或SysTick实现
    // 这里简化处理，实际应该初始化SysTick
    static uint32_t tick = 0;
    // 延时模拟
    for(volatile int i=0; i<1000; i++);
    return tick++;
}

void HAL_Delay(uint32_t ms)
{
    for(uint32_t i=0; i<ms; i++) {
        for(volatile int j=0; j<8000; j++);
    }
}

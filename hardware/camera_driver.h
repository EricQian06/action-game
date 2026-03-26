/**
 * STM32F103VE 摄像头驱动头文件
 */

#ifndef __CAMERA_DRIVER_H__
#define __CAMERA_DRIVER_H__

#include <stdint.h>

// ============================================
// 宏定义
// ============================================

// I2C地址
#define OV_I2C_ADDR         0x42
#define OV_WRITE_ADDR       0x42
#define OV_READ_ADDR        0x43

// OV寄存器
#define OV_REG_PID          0x0A
#define OV_REG_VER          0x0B
#define OV_REG_COM7         0x12
#define OV_REG_CLKRC        0x11

// SCCB宏
#define SCCB_SIO_C_H()      GPIO_SetBits(SCCB_GPIO_PORT, SCCB_SIO_C_PIN)
#define SCCB_SIO_C_L()      GPIO_ResetBits(SCCB_GPIO_PORT, SCCB_SIO_C_PIN)
#define SCCB_SIO_D_H()      GPIO_SetBits(SCCB_GPIO_PORT, SCCB_SIO_D_PIN)
#define SCCB_SIO_D_L()      GPIO_ResetBits(SCCB_GPIO_PORT, SCCB_SIO_D_PIN)
#define SCCB_SIO_D_READ()   GPIO_ReadInputDataBit(SCCB_GPIO_PORT, SCCB_SIO_D_PIN)

// 命令定义
#define CMD_HANDSHAKE       0x01
#define CMD_START_CAPTURE   0x02
#define CMD_STOP_CAPTURE    0x03
#define CMD_IMAGE_DATA      0x04
#define CMD_CONFIG_CAMERA   0x05
#define CMD_STATUS_REQ      0x06
#define CMD_STATUS_RSP      0x07
#define CMD_ERROR           0x08
#define CMD_RESET           0x09
#define CMD_READY           0x0A

// ============================================
// 类型定义
// ============================================

typedef enum {
    RES_QQVGA = 0,      // 160x120
    RES_QVGA = 1,       // 320x240
    RES_VGA = 2,        // 640x480
    RES_SVGA = 3,       // 800x600
    RES_XGA = 4         // 1024x768
} ImageResolution;

typedef enum {
    CAM_STATE_IDLE = 0,
    CAM_STATE_CAPTURING,
    CAM_STATE_PROCESSING,
    CAM_STATE_SENDING
} CameraState;

typedef struct {
    ImageResolution resolution;
    uint8_t quality;
    uint8_t brightness;
} ImageConfig;

// ============================================
// 函数声明
// ============================================

// 初始化函数
void Camera_Init(void);
uint8_t Camera_Capture(uint8_t *buffer, uint32_t *size);
void Camera_Config(ImageResolution res);

// SCCB接口
uint8_t SCCB_WriteReg(uint8_t reg, uint8_t data);
uint8_t SCCB_ReadReg(uint8_t reg);

// 串口命令处理
void CMD_Process(uint8_t *rx_buffer, uint16_t rx_len);
void CMD_SendResponse(uint8_t cmd, uint8_t *data, uint16_t len);
void CMD_SendImagePacket(uint16_t seq, uint16_t total, uint8_t *data, uint16_t len);

// 辅助函数
void Delay_ms(uint32_t ms);
void Delay_us(uint32_t us);

// OV7670初始化配置数组
static const uint8_t OV7670_QVGA[][2] = {
    {0x12, 0x80},  // 复位
    {0x11, 0x01},  // 时钟
    {0x12, 0x14},  // QVGA RGB
    {0x0C, 0x04},  // DCW使能
    {0x40, 0x10},  // RGB565
    {0x3E, 0x1A},  // 缩放
    {0x70, 0x3A},  // 水平缩放
    {0x71, 0x35},  // 垂直缩放
    {0x72, 0x11},  // 水平缩放控制
    {0x73, 0xF0},  // 垂直缩放控制
    {0xFF, 0xFF}   // 结束
};

// OV7725初始化配置数组
static const uint8_t OV7725_QVGA[][2] = {
    {0x12, 0x80},  // 复位
    {0x3D, 0x03},  // 时钟设置
    {0x17, 0x22},  // HSTART
    {0x18, 0xA4},  // HSIZE
    {0x19, 0x07},  // VSTRT
    {0x1A, 0xF0},  // VSIZE
    {0x12, 0x14},  // QVGA
    {0x11, 0x40},  // 时钟
    {0x32, 0x80},  // 水平镜像
    {0x0C, 0x10},  // DCW
    {0xFF, 0xFF}   // 结束
};

#endif /* __CAMERA_DRIVER_H__ */

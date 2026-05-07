#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OV7725图像接收程序
功能：接收STM32发送的压缩图像数据，解压并显示
"""

import serial
import time
import cv2
import numpy as np

class ImageReceiver:
    def __init__(self, port='COM3', baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
    
    def connect(self):
        """连接串口"""
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=5)
            print(f"成功连接到 {self.port}")
            return True
        except Exception as e:
            print(f"连接失败: {e}")
            return False
    
    def receive_image(self):
        """接收图像数据"""
        print("等待接收图像...")
        
        # 等待帧头
        while True:
            line = self.ser.readline().decode('utf-8', errors='ignore').strip()
            if line == 'IMG_START':
                print("开始接收图像数据")
                break
        
        # 读取图像信息
        width = 0
        height = 0
        color_format = 'grayscale'  # 默认灰度
        
        while True:
            line = self.ser.readline().decode('utf-8', errors='ignore').strip()
            if line.startswith('WIDTH:'):
                width = int(line.split(':')[1])
            elif line.startswith('HEIGHT:'):
                height = int(line.split(':')[1])
            elif line.startswith('FORMAT:'):
                color_format = line.split(':')[1].strip()
            elif line == 'DATA:':
                break
        
        print(f"图像尺寸: {width}x{height}, 格式: {color_format}")
        
        # 读取压缩数据
        compressed_data = b''
        while True:
            line = self.ser.readline().decode('utf-8', errors='ignore').strip()
            if line == 'IMG_END':
                break
            # 将十六进制字符串转换为字节
            try:
                compressed_data += bytes.fromhex(line)
            except:
                pass
        
        print(f"接收到压缩数据: {len(compressed_data)} 字节")
        return width, height, compressed_data, color_format
    
    def decompress_rle(self, compressed_data, width, height, color_format='grayscale'):
        """解压RLE压缩数据"""
        data = []
        i = 0
        
        if color_format == 'rgb565':
            # RGB565格式，每个像素2字节
            total_bytes = width * height * 2
            while len(data) < total_bytes and i < len(compressed_data):
                count = compressed_data[i]
                # RGB565每个像素2字节
                value1 = compressed_data[i+1]
                value2 = compressed_data[i+2] if i+2 < len(compressed_data) else 0
                data.extend([value1, value2] * count)
                i += 3
            # 确保数据长度正确
            data = data[:total_bytes]
            # 转换为numpy数组并重塑为(height, width, 2)
            img = np.array(data, dtype=np.uint8).reshape((height, width, 2))
            # RGB565转RGB888
            img = self.rgb565_to_rgb888(img)
        else:
            # 灰度格式，每个像素1字节
            total_pixels = width * height
            while len(data) < total_pixels and i < len(compressed_data):
                count = compressed_data[i]
                value = compressed_data[i+1]
                data.extend([value] * count)
                i += 2
            # 确保数据长度正确
            data = data[:total_pixels]
            # 转换为numpy数组并重塑
            img = np.array(data, dtype=np.uint8).reshape((height, width))
        
        return img
    
    def rgb565_to_rgb888(self, img_rgb565):
        """将RGB565格式转换为RGB888格式"""
        # 分离高字节和低字节
        high = img_rgb565[:, :, 0]
        low = img_rgb565[:, :, 1]
        
        # 提取RGB分量
        r = ((high >> 3) & 0x1F) << 3
        g = (((high & 0x07) << 3) | ((low >> 5) & 0x07)) << 2
        b = (low & 0x1F) << 3
        
        # 合并为RGB图像
        img_rgb = np.stack([r, g, b], axis=2).astype(np.uint8)
        return img_rgb
    
    def enhance_image(self, img):
        """增强图像对比度和亮度"""
        if len(img.shape) == 3 and img.shape[2] == 3:
            # 彩色图像：转换为YUV空间，对亮度通道进行直方图均衡化
            img_yuv = cv2.cvtColor(img, cv2.COLOR_RGB2YUV)
            img_yuv[:, :, 0] = cv2.equalizeHist(img_yuv[:, :, 0])
            enhanced = cv2.cvtColor(img_yuv, cv2.COLOR_YUV2RGB)
        else:
            # 灰度图像：直接进行直方图均衡化
            enhanced = cv2.equalizeHist(img)
        return enhanced
    
    def display_image(self, img):
        """显示图像"""
        cv2.imshow('OV7725 Image', img)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    
    def save_image(self, img, filename='captured_image.jpg'):
        """保存图像"""
        cv2.imwrite(filename, img)
        print(f"图像已保存为 {filename}")
    
    def close(self):
        """关闭串口"""
        if self.ser:
            self.ser.close()
            print("串口已关闭")

def main():
    # 创建接收器实例
    receiver = ImageReceiver(port='COM3')  # 根据实际串口修改
    
    if not receiver.connect():
        return
    
    try:
        while True:
            # 接收图像
            width, height, compressed_data, color_format = receiver.receive_image()
            
            # 解压图像
            img = receiver.decompress_rle(compressed_data, width, height, color_format)
            
            # 增强图像对比度和亮度
            img = receiver.enhance_image(img)
            
            # 显示和保存图像
            receiver.display_image(img)
            receiver.save_image(img)
            
            print("等待下一张图像...")
            time.sleep(1)
    except KeyboardInterrupt:
        print("程序被用户中断")
    finally:
        receiver.close()

if __name__ == "__main__":
    main()

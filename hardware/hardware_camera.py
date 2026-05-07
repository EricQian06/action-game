#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
硬件摄像头服务模块
功能：通过串口与STM32通信，发送拍照指令并接收图像

使用方式：
    from hardware_camera import HardwareCamera
    cam = HardwareCamera(port='COM3')
    success = cam.capture(output_path='../server/input.jpg')
"""

import serial
import time
import cv2
import numpy as np
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HardwareCamera:
    """硬件摄像头控制类"""

    def __init__(self, port='COM3', baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.ser = None

    def connect(self):
        """连接串口"""
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=10)
            logger.info(f"成功连接到串口 {self.port}")
            return True
        except Exception as e:
            logger.error(f"串口连接失败: {e}")
            return False

    def disconnect(self):
        """断开串口连接"""
        if self.ser:
            self.ser.close()
            self.ser = None
            logger.info("串口已断开")

    def _clear_buffer(self):
        """清空串口接收缓冲区"""
        if self.ser:
            self.ser.reset_input_buffer()

    def send_capture_command(self):
        """发送拍照指令 'C' 给STM32"""
        if not self.ser:
            logger.error("串口未连接")
            return False
        try:
            self.ser.write(b'C')
            logger.info("已发送拍照指令 'C'")
            return True
        except Exception as e:
            logger.error(f"发送指令失败: {e}")
            return False

    def receive_image(self):
        """接收图像数据"""
        if not self.ser:
            logger.error("串口未连接")
            return None

        logger.info("等待接收图像...")

        # 等待帧头 IMG_START
        start_time = time.time()
        while True:
            if time.time() - start_time > 10:
                logger.error("等待帧头超时")
                return None

            line = self.ser.readline().decode('utf-8', errors='ignore').strip()
            if line == 'IMG_START':
                logger.info("开始接收图像数据")
                break

        # 读取图像信息
        width = 0
        height = 0
        color_format = 'grayscale'

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

        logger.info(f"图像尺寸: {width}x{height}, 格式: {color_format}")

        # 读取压缩数据
        compressed_data = b''
        while True:
            line = self.ser.readline().decode('utf-8', errors='ignore').strip()
            if line == 'IMG_END':
                break
            try:
                compressed_data += bytes.fromhex(line)
            except:
                pass

        logger.info(f"接收到压缩数据: {len(compressed_data)} 字节")
        return width, height, compressed_data, color_format

    def decompress_rle(self, compressed_data, width, height, color_format='grayscale'):
        """解压RLE压缩数据"""
        data = []
        i = 0

        if color_format == 'rgb565':
            total_bytes = width * height * 2
            while len(data) < total_bytes and i < len(compressed_data):
                count = compressed_data[i]
                value1 = compressed_data[i+1]
                value2 = compressed_data[i+2] if i+2 < len(compressed_data) else 0
                data.extend([value1, value2] * count)
                i += 3
            data = data[:total_bytes]
            img = np.array(data, dtype=np.uint8).reshape((height, width, 2))
            img = self.rgb565_to_rgb888(img)
        else:
            total_pixels = width * height
            while len(data) < total_pixels and i < len(compressed_data):
                count = compressed_data[i]
                value = compressed_data[i+1]
                data.extend([value] * count)
                i += 2
            data = data[:total_pixels]
            img = np.array(data, dtype=np.uint8).reshape((height, width))

        return img

    def rgb565_to_rgb888(self, img_rgb565):
        """RGB565转RGB888"""
        high = img_rgb565[:, :, 0]
        low = img_rgb565[:, :, 1]
        r = ((high >> 3) & 0x1F) << 3
        g = (((high & 0x07) << 3) | ((low >> 5) & 0x07)) << 2
        b = (low & 0x1F) << 3
        img_rgb = np.stack([r, g, b], axis=2).astype(np.uint8)
        return img_rgb

    def enhance_image(self, img):
        """增强图像对比度和亮度"""
        if len(img.shape) == 3 and img.shape[2] == 3:
            img_yuv = cv2.cvtColor(img, cv2.COLOR_RGB2YUV)
            img_yuv[:, :, 0] = cv2.equalizeHist(img_yuv[:, :, 0])
            enhanced = cv2.cvtColor(img_yuv, cv2.COLOR_YUV2RGB)
        else:
            enhanced = cv2.equalizeHist(img)
        return enhanced

    def capture(self, output_path=None, timeout=15):
        """
        完整拍照流程：发送指令 -> 接收图像 -> 保存

        Args:
            output_path: 保存路径，默认为 '../server/input.jpg'
            timeout: 接收超时时间（秒）

        Returns:
            dict: {'success': bool, 'path': str, 'message': str}
        """
        if output_path is None:
            # 默认保存到 server/input.jpg
            base_dir = os.path.dirname(os.path.abspath(__file__))
            output_path = os.path.join(base_dir, '..', 'server', 'input.jpg')
        output_path = os.path.abspath(output_path)

        # 确保目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # 连接串口
        if not self.connect():
            return {'success': False, 'path': None, 'message': '串口连接失败'}

        try:
            # 清空缓冲区
            self._clear_buffer()

            # 发送拍照指令
            if not self.send_capture_command():
                return {'success': False, 'path': None, 'message': '发送拍照指令失败'}

            # 接收图像
            result = self.receive_image()
            if result is None:
                return {'success': False, 'path': None, 'message': '接收图像失败或超时'}

            width, height, compressed_data, color_format = result

            # 解压图像
            img = self.decompress_rle(compressed_data, width, height, color_format)

            # 增强图像
            img = self.enhance_image(img)

            # 保存图像
            write_success = cv2.imwrite(output_path, img)
            if not write_success:
                # OpenCV 在 Windows 上不支持中文路径，使用 imencode + 原生写入作为 fallback
                try:
                    ext = os.path.splitext(output_path)[1].lower()
                    if ext in ['.jpg', '.jpeg']:
                        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 95]
                        is_ok, buf = cv2.imencode('.jpg', img, encode_param)
                    elif ext == '.png':
                        is_ok, buf = cv2.imencode('.png', img)
                    else:
                        is_ok, buf = cv2.imencode('.jpg', img)

                    if is_ok:
                        with open(output_path, 'wb') as f:
                            f.write(buf.tobytes())
                        write_success = True
                        logger.info("使用 imencode fallback 保存图像成功")
                    else:
                        logger.error("cv2.imencode 也失败了")
                except Exception as e:
                    logger.error(f"imencode fallback 保存出错: {e}")

            if not write_success:
                logger.error(f"cv2.imwrite 返回失败，图像可能为空或损坏")
                return {'success': False, 'path': None, 'message': '图像保存失败（cv2.imwrite返回False）'}

            # 验证文件是否真的存在
            if not os.path.exists(output_path):
                logger.error(f"文件未生成: {output_path}")
                return {'success': False, 'path': None, 'message': '图像文件未生成'}

            logger.info(f"图像已保存: {output_path} ({os.path.getsize(output_path)} 字节)")

            return {
                'success': True,
                'path': output_path,
                'message': f'拍照成功，图像尺寸: {width}x{height}'
            }

        except Exception as e:
            logger.error(f"拍照过程出错: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'path': None, 'message': f'拍照出错: {str(e)}'}

        finally:
            self.disconnect()


# 全局单例（Flask使用）
_hardware_camera = None

def get_hardware_camera(port='COM3'):
    """获取硬件摄像头实例（全局单例）"""
    global _hardware_camera
    if _hardware_camera is None:
        _hardware_camera = HardwareCamera(port=port)
    return _hardware_camera


def capture_with_hardware(output_path=None, port='COM3'):
    """
    便捷函数：使用硬件摄像头拍照

    Args:
        output_path: 保存路径
        port: 串口号

    Returns:
        dict: 拍照结果
    """
    cam = HardwareCamera(port=port)
    return cam.capture(output_path)


if __name__ == "__main__":
    # 测试：直接运行进行硬件拍照测试
    print("硬件摄像头测试模式")
    print("=" * 40)
    result = capture_with_hardware()
    print(f"结果: {result}")

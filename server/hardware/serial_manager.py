"""
串口管理器
负责与STM32开发板通过串口通信，控制摄像头拍照和传输图像数据
"""
import serial
import serial.tools.list_ports
import struct
import threading
import logging
import time
from typing import Optional, Callable, List, Dict, Tuple
from enum import Enum
from dataclasses import dataclass

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    SERIAL_BAUDRATE, SERIAL_TIMEOUT, SERIAL_READ_SIZE,
    IMAGE_PACKET_SIZE, MAX_IMAGE_SIZE
)

logger = logging.getLogger(__name__)


class Command(Enum):
    """串口命令定义"""
    HANDSHAKE = 0x01
    START_CAPTURE = 0x02
    STOP_CAPTURE = 0x03
    IMAGE_DATA = 0x04
    CONFIG_CAMERA = 0x05
    STATUS_REQ = 0x06
    STATUS_RSP = 0x07
    ERROR = 0x08
    RESET = 0x09
    READY = 0x0A


@dataclass
class FrameHeader:
    """数据帧头"""
    START_BYTE_1 = 0xAA
    START_BYTE_2 = 0x55
    END_BYTE_1 = 0x0D
    END_BYTE_2 = 0x0A


class SerialManager:
    """串口管理器类"""

    def __init__(self, port: str = None, baudrate: int = SERIAL_BAUDRATE,
                 timeout: float = SERIAL_TIMEOUT):
        """
        初始化串口管理器

        Args:
            port: 串口号，如'COM3'或'/dev/ttyUSB0'
            baudrate: 波特率
            timeout: 超时时间(秒)
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout

        self.serial: Optional[serial.Serial] = None
        self.connected = False
        self.camera_ready = False

        # 接收缓冲区
        self.receive_buffer = bytearray()
        self.image_buffer = bytearray()
        self.expected_packets = 0
        self.received_packets = 0

        # 回调函数
        self.on_image_received: Optional[Callable[[bytes], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None

        # 接收线程
        self.receive_thread: Optional[threading.Thread] = None
        self.running = False

        logger.info(f'串口管理器已创建: port={port}, baudrate={baudrate}')

    def find_stm32_port(self) -> Optional[str]:
        """自动查找STM32串口"""
        ports = serial.tools.list_ports.comports()

        for port in ports:
            # 检查常见的STM32标识
            if any(keyword in port.description.upper() for keyword in
                   ['STM32', 'VCP', 'VIRTUAL COM', 'USB SERIAL']):
                logger.info(f'找到STM32设备: {port.device} - {port.description}')
                return port.device

            # Windows下常见串口
            if port.device.startswith('COM') and port.description != 'n/a':
                # 尝试连接测试
                try:
                    test_serial = serial.Serial(port.device, self.baudrate, timeout=1)
                    # 发送握手命令
                    test_serial.write(b'\xAA\x55\x01\x00\x00\xAC\x0D\x0A')
                    response = test_serial.read(8)
                    test_serial.close()

                    if len(response) >= 8:
                        logger.info(f'通过测试找到STM32: {port.device}')
                        return port.device
                except:
                    pass

        # 如果没有找到特定标识，返回第一个可用串口
        if ports:
            port = ports[0]
            logger.info(f'使用第一个可用串口: {port.device}')
            return port.device

        return None

    def connect(self, port: str = None) -> bool:
        """
        连接串口

        Args:
            port: 串口号，如果为None则使用初始化时的端口或自动查找

        Returns:
            是否连接成功
        """
        if port:
            self.port = port

        if not self.port:
            # 自动查找
            self.port = self.find_stm32_port()
            if not self.port:
                logger.error('未找到可用的STM32串口')
                return False

        try:
            # 关闭现有连接
            if self.serial and self.serial.is_open:
                self.serial.close()

            # 打开串口
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout
            )

            self.connected = True
            logger.info(f'串口已连接: {self.port} @ {self.baudrate}bps')

            # 启动接收线程
            self.running = True
            self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self.receive_thread.start()

            # 发送握手命令
            self.send_command(Command.HANDSHAKE)

            return True

        except serial.SerialException as e:
            logger.error(f'串口连接失败: {e}')
            self.connected = False
            return False

    def disconnect(self):
        """断开串口连接"""
        self.running = False

        if self.receive_thread and self.receive_thread.is_alive():
            self.receive_thread.join(timeout=2)

        if self.serial and self.serial.is_open:
            self.serial.close()

        self.connected = False
        self.camera_ready = False
        logger.info('串口已断开')

    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self.connected and self.serial and self.serial.is_open

    def send_command(self, command: Command, data: bytes = None) -> bool:
        """
        发送命令到STM32

        Args:
            command: 命令类型
            data: 附加数据

        Returns:
            是否发送成功
        """
        if not self.is_connected():
            logger.error('串口未连接，无法发送命令')
            return False

        try:
            # 构建帧
            frame = bytearray()
            frame.append(FrameHeader.START_BYTE_1)
            frame.append(FrameHeader.START_BYTE_2)
            frame.append(command.value)

            # 数据长度
            data_len = len(data) if data else 0
            frame.append(data_len & 0xFF)
            frame.append((data_len >> 8) & 0xFF)

            # 数据
            if data:
                frame.extend(data)

            # 校验和 (从帧头到数据的累加和)
            checksum = sum(frame) & 0xFF
            frame.append(checksum)

            # 帧尾
            frame.append(FrameHeader.END_BYTE_1)
            frame.append(FrameHeader.END_BYTE_2)

            # 发送
            self.serial.write(frame)
            logger.debug(f'命令已发送: {command.name} ({command.value:02X})')
            return True

        except serial.SerialException as e:
            logger.error(f'发送命令失败: {e}')
            return False

    def _receive_loop(self):
        """接收数据的后台线程"""
        logger.info('接收线程已启动')

        while self.running and self.is_connected():
            try:
                # 读取数据
                if self.serial.in_waiting > 0:
                    data = self.serial.read(min(self.serial.in_waiting, SERIAL_READ_SIZE))
                    self.receive_buffer.extend(data)

                    # 处理缓冲区数据
                    self._process_buffer()

                # 短暂休眠避免CPU占用过高
                time.sleep(0.01)

            except serial.SerialException as e:
                logger.error(f'接收数据错误: {e}')
                self.connected = False
                break
            except Exception as e:
                logger.error(f'接收线程异常: {e}')

        logger.info('接收线程已停止')

    def _process_buffer(self):
        """处理接收缓冲区"""
        while len(self.receive_buffer) >= 8:  # 最小帧长度
            # 查找帧头
            start_idx = 0
            found = False

            while start_idx < len(self.receive_buffer) - 1:
                if (self.receive_buffer[start_idx] == FrameHeader.START_BYTE_1 and
                    self.receive_buffer[start_idx + 1] == FrameHeader.START_BYTE_2):
                    found = True
                    break
                start_idx += 1

            if not found:
                # 没有找到帧头，清空缓冲区
                self.receive_buffer.clear()
                return

            # 丢弃帧头之前的数据
            if start_idx > 0:
                self.receive_buffer = self.receive_buffer[start_idx:]

            # 检查是否有足够的数据
            if len(self.receive_buffer) < 5:
                return

            # 解析帧头
            cmd = self.receive_buffer[2]
            data_len = self.receive_buffer[3] | (self.receive_buffer[4] << 8)

            # 计算总帧长度
            total_len = 5 + data_len + 3  # 头5字节 + 数据 + 校验和1字节 + 帧尾2字节

            if len(self.receive_buffer) < total_len:
                # 数据不完整，等待更多数据
                return

            # 提取完整帧
            frame = self.receive_buffer[:total_len]

            # 验证校验和
            checksum = sum(frame[:-3]) & 0xFF
            if checksum != frame[-3]:
                logger.warning(f'校验和错误，丢弃帧: cmd={cmd:02X}')
                self.receive_buffer = self.receive_buffer[1:]  # 丢弃帧头，继续处理
                continue

            # 提取数据
            data = frame[5:5+data_len] if data_len > 0 else b''

            # 处理命令
            self._handle_command(cmd, data)

            # 从缓冲区移除已处理的帧
            self.receive_buffer = self.receive_buffer[total_len:]

    def _handle_command(self, cmd: int, data: bytes):
        """处理接收到的命令"""
        try:
            command = Command(cmd)
            logger.debug(f'收到命令: {command.name} ({cmd:02X}), 数据长度: {len(data)}')

            if command == Command.HANDSHAKE:
                # 握手响应
                logger.info('收到握手响应')
                self.camera_ready = True

            elif command == Command.STATUS_RSP:
                # 状态响应
                if len(data) >= 2:
                    status = data[0]
                    self.camera_ready = (status & 0x01) != 0
                    logger.info(f'设备状态: camera_ready={self.camera_ready}')

            elif command == Command.IMAGE_DATA:
                # 图像数据包
                self._handle_image_data(data)

            elif command == Command.ERROR:
                # 错误报告
                error_code = data[0] if data else 0
                logger.error(f'设备报告错误: {error_code:02X}')
                if self.on_error:
                    self.on_error(f'Device error: {error_code:02X}')

            elif command == Command.READY:
                # 设备就绪
                logger.info('设备已就绪')
                self.camera_ready = True

            else:
                logger.warning(f'未处理的命令: {command.name}')

        except ValueError:
            logger.warning(f'未知命令: {cmd:02X}')
        except Exception as e:
            logger.error(f'处理命令失败: {e}')

    def _handle_image_data(self, data: bytes):
        """处理图像数据包"""
        try:
            if len(data) < 4:
                logger.warning('图像数据包太短')
                return

            # 解析包头
            packet_seq = struct.unpack('<H', data[0:2])[0]
            total_packets = struct.unpack('<H', data[2:4])[0]
            image_data = data[4:]

            # 初始化接收状态
            if packet_seq == 1:
                self.image_buffer = bytearray()
                self.expected_packets = total_packets
                self.received_packets = 0
                logger.info(f'开始接收图像，共 {total_packets} 包')

            # 添加数据到缓冲区
            self.image_buffer.extend(image_data)
            self.received_packets += 1

            logger.debug(f'收到图像数据包: {packet_seq}/{total_packets}')

            # 检查是否接收完成
            if self.received_packets >= self.expected_packets:
                logger.info(f'图像接收完成，总大小: {len(self.image_buffer)} 字节')

                # 验证图像数据
                if len(self.image_buffer) > 0:
                    # 检查JPEG头
                    if self.image_buffer[0:2] == b'\xff\xd8':
                        # 调用回调
                        if self.on_image_received:
                            self.on_image_received(bytes(self.image_buffer))
                    else:
                        logger.warning('接收到的数据不是有效的JPEG图像')
                else:
                    logger.warning('接收到的图像数据为空')

                # 重置缓冲区
                self.image_buffer = bytearray()
                self.expected_packets = 0
                self.received_packets = 0

        except Exception as e:
            logger.error(f'处理图像数据包失败: {e}')

    def capture_image(self, timeout: float = 10.0) -> Optional[bytes]:
        """
        触发拍照并等待接收图像

        Args:
            timeout: 超时时间(秒)

        Returns:
            图像数据(JPEG格式)，超时返回None
        """
        if not self.is_connected():
            logger.error('串口未连接，无法拍照')
            return None

        if not self.camera_ready:
            logger.warning('摄像头未就绪，尝试发送准备命令')
            # 发送状态请求
            self.send_command(Command.STATUS_REQ)
            time.sleep(0.5)

        # 重置图像缓冲区
        self.image_buffer = bytearray()
        self.expected_packets = 0
        self.received_packets = 0

        # 设置结果存储
        result = {'image': None}

        def image_callback(image_data: bytes):
            result['image'] = image_data

        # 临时设置回调
        original_callback = self.on_image_received
        self.on_image_received = image_callback

        try:
            # 发送拍照命令
            logger.info('发送拍照命令')
            success = self.send_command(Command.START_CAPTURE)

            if not success:
                logger.error('发送拍照命令失败')
                return None

            # 等待接收图像
            start_time = time.time()
            while result['image'] is None and (time.time() - start_time) < timeout:
                time.sleep(0.1)

            if result['image'] is None:
                logger.error(f'接收图像超时({timeout}秒)')
                return None

            logger.info(f'成功接收图像，大小: {len(result["image"])} 字节')
            return result['image']

        finally:
            # 恢复原始回调
            self.on_image_received = original_callback

    def configure_camera(self, resolution: str = 'VGA',
                        quality: int = 85,
                        brightness: int = 50) -> bool:
        """
        配置摄像头参数

        Args:
            resolution: 分辨率 (QQVGA, QVGA, VGA, SVGA)
            quality: JPEG质量 (0-100)
            brightness: 亮度 (0-100)

        Returns:
            是否配置成功
        """
        # 构建配置数据
        config_data = struct.pack('<B', self._get_resolution_code(resolution))
        config_data += struct.pack('<B', quality)
        config_data += struct.pack('<B', brightness)

        return self.send_command(Command.CONFIG_CAMERA, config_data)

    def _get_resolution_code(self, resolution: str) -> int:
        """获取分辨率代码"""
        codes = {
            'QQVGA': 0,  # 160x120
            'QVGA': 1,   # 320x240
            'VGA': 2,    # 640x480
            'SVGA': 3,   # 800x600
            'XGA': 4,    # 1024x768
        }
        return codes.get(resolution.upper(), 2)  # 默认VGA

    def reset(self) -> bool:
        """重置设备"""
        return self.send_command(Command.RESET)

    def get_status(self) -> Dict:
        """获取设备状态"""
        self.send_command(Command.STATUS_REQ)
        # 状态响应会在_handle_command中处理
        return {
            'connected': self.connected,
            'camera_ready': self.camera_ready
        }


# 辅助函数
def list_serial_ports():
    """列出所有可用的串口"""
    ports = serial.tools.list_ports.comports()
    result = []

    for port in ports:
        result.append({
            'device': port.device,
            'description': port.description,
            'hwid': port.hwid,
            'vid': port.vid,
            'pid': port.pid
        })

    return result


def test_connection(port: str, baudrate: int = SERIAL_BAUDRATE) -> bool:
    """测试串口连接"""
    try:
        ser = serial.Serial(port, baudrate, timeout=2)

        # 发送简单的握手
        test_data = b'\xAA\x55\x01\x00\x00\xAC\x0D\x0A'
        ser.write(test_data)

        # 等待响应
        response = ser.read(8)
        ser.close()

        return len(response) >= 8

    except:
        return False

"""
STM32 按键检测脚本 (K1=登录, K2=注册)
通过 USB CDC (虚拟串口) 与 STM32 通信
当检测到按键按下时，自动向 Flask 服务器发送对应的 HTTP 请求

依赖安装:
pip install pyserial requests
"""

import serial
import time
import requests
import threading

# ================= 配置区域 =================
# 1. 串口配置 (根据你的电脑实际端口修改)
# Windows 示例: 'COM3', 'COM4'
# Linux/Mac 示例: '/dev/ttyACM0', '/dev/ttyUSB0', '/dev/cu.usbmodem...'
SERIAL_PORT = 'COM5'  
BAUD_RATE = 9600

# 2. Flask 服务器地址
FLASK_URL = 'http://127.0.0.1:5000'

# 3. 按键定义 (根据 STM32 固件返回的字符定义)
# 假设 STM32 按下 K1 发送字符 '1', 按下 K2 发送字符 '2'
KEY_K1 = b'1'
KEY_K2 = b'2'
# ===========================================

class STM32KeyListener:
    def __init__(self, port, baudrate):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.running = False
        
    def connect(self):
        """连接串口"""
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(2)  # 等待串口初始化
            print(f"✓ 成功连接到串口: {self.port}")
            return True
        except serial.SerialException as e:
            print(f"✗ 无法打开串口 {self.port}: {e}")
            print("请检查:")
            print("  1. 单片机是否已连接电脑")
            print("  2. 端口号是否正确 (设备管理器中查看)")
            print("  3. 是否有其他程序占用了该串口")
            return False
            
    def send_login_request(self, username, password):
        """发送 K1 登录请求"""
        try:
            response = requests.post(
                f"{FLASK_URL}/api/k1_login",
                data={'username': username, 'password': password},
                timeout=5
            )
            result = response.json()
            status = "✓" if result.get('status') == 'success' else "✗"
            print(f"{status} 登录结果: {result.get('message')}")
        except Exception as e:
            print(f"✗ 登录请求失败: {e}")
            
    def send_register_request(self, username, password):
        """发送 K2 注册请求"""
        try:
            response = requests.post(
                f"{FLASK_URL}/api/k2_register",
                data={'username': username, 'password': password},
                timeout=5
            )
            result = response.json()
            status = "✓" if result.get('status') == 'success' else "✗"
            print(f"{status} 注册结果: {result.get('message')}")
        except Exception as e:
            print(f"✗ 注册请求失败: {e}")
    
    def get_input_from_browser(self):
        """
        从浏览器获取当前输入的用户名和密码
        这里使用一个简单的轮询方式，实际项目中可以优化
        由于跨域限制，最简单的方式是让用户在控制台输入，或者使用 Selenium
        这里为了简化，我们假设用户在运行脚本后，在终端输入一次账号密码
        """
        print("\n--- 首次运行请输入账号信息 ---")
        username = input("请输入用户名: ").strip()
        password = input("请输入密码: ").strip()
        return username, password
    
    def listen(self):
        """监听串口数据"""
        if not self.ser:
            return
            
        print(f"\n开始监听按键 (K1='{KEY_K1.decode()}', K2='{KEY_K2.decode()}')...")
        print("按 Ctrl+C 停止")
        
        # 获取一次账号密码
        username, password = self.get_input_from_browser()
        print(f"当前使用账号: {username} (如需修改请重启脚本)\n")
        
        self.running = True
        try:
            while self.running:
                if self.ser.in_waiting > 0:
                    data = self.ser.read(1)
                    
                    if data == KEY_K1:
                        print("\n[检测到 K1 按下] -> 执行登录")
                        self.send_login_request(username, password)
                        
                    elif data == KEY_K2:
                        print("\n[检测到 K2 按下] -> 执行注册")
                        self.send_register_request(username, password)
                        
        except KeyboardInterrupt:
            print("\n停止监听...")
        finally:
            self.running = False
            if self.ser and self.ser.is_open:
                self.ser.close()
                print("串口已关闭")

def main():
    print("=" * 50)
    print("STM32 按键检测程序 (K1=登录, K2=注册)")
    print("=" * 50)
    
    # 创建监听器
    listener = STM32KeyListener(SERIAL_PORT, BAUD_RATE)
    
    # 连接串口
    if not listener.connect():
        # 尝试自动查找可用串口
        import serial.tools.list_ports
        ports = list(serial.tools.list_ports.comports())
        if ports:
            print("\n检测到的可用串口:")
            for p in ports:
                print(f"  - {p.device}: {p.description}")
            print("\n请修改代码中的 SERIAL_PORT 变量后重新运行")
        else:
            print("\n未检测到任何串口设备")
        return
    
    # 开始监听
    listener.listen()

if __name__ == '__main__':
    main()

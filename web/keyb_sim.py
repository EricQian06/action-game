# keyb_sim.py
import threading
import requests
from pynput import keyboard

BACKEND_URL = "http://127.0.0.1:5000/api/action"

def send_action(action_type):
    """只发送动作类型，不携带账号密码"""
    print(f"\n[模拟硬件] 按下按键 -> 触发 {action_type.upper()}")
    
    try:
        # 只发送动作类型，账号密码由后端从当前会话/缓存中获取
        resp = requests.post(BACKEND_URL, json={"action": action_type}, timeout=2)
        if resp.status_code == 200:
            data = resp.json()
            print(f"[模拟硬件] 结果: {data.get('message')}")
        else:
            print(f"[模拟硬件] 错误: {resp.json().get('message')}")
    except Exception as e:
        print(f"[模拟硬件] 连接失败: {e}")

def on_press(key):
    try:
        if key == keyboard.Key.f1:
            send_action("login")
        elif key == keyboard.Key.f2:
            send_action("register")
    except Exception as e:
        print(f"监听出错: {e}")

def start_keyboard_simulation():
    def run_listener():
        with keyboard.Listener(on_press=on_press) as listener:
            listener.join()
    
    t = threading.Thread(target=run_listener, daemon=True)
    t.start()
    print("[系统] 键盘模拟已启动 (F1=登录, F2=注册)")

if __name__ == "__main__":
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()
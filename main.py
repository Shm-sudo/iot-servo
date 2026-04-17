# main.py
import paho.mqtt.client as mqtt
import json
import time
import hmac
import hashlib

from kivy.app import App
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from kivy.core.window import Window

# ===========================================
# 配置你的华为云IoT连接信息
# ===========================================
DEVICE_ID = "69d74023e094d61592300e4c_phone_controller"
DEVICE_SECRET = "12345678"  # 请替换为华为云控制台里的真实设备密钥
SERVER = "22f19faf90.st1.iotda-device.cn-east-3.myhuaweicloud.com"
PORT = 1883  # 非加密端口

# ===========================================

def generate_iotda_mqtt_params(device_id, device_secret):
    """
    生成华为云 IoTDA 动态 MQTT 密码
    注意：华为云使用非标准的 HMAC 方式：key=时间戳，message=设备密钥
    """
    timestamp = time.strftime("%Y%m%d%H", time.gmtime())
    password = hmac.new(
        timestamp.encode('utf-8'),
        device_secret.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    client_id = f"{device_id}_0_0_{timestamp}"
    username = device_id
    print(f"Timestamp: {timestamp}, Password (first 8): {password[:8]}...")
    return client_id, username, password

class MQTTClient:
    def __init__(self):
        client_id, username, password = generate_iotda_mqtt_params(DEVICE_ID, DEVICE_SECRET)
        
        # 消除弃用警告
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.username_pw_set(username, password)
        
        try:
            print(f"Connecting to: {SERVER}:{PORT}")
            self.client.connect(SERVER, PORT, 60)
        except Exception as e:
            print(f"Connection init failed: {e}")
            
        self.client.loop_start()
        self.connected = False

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            print("✅ MQTT connected")
        else:
            self.connected = False
            print(f"❌ MQTT connection failed, rc: {rc}")

    def on_disconnect(self, client, userdata, rc):
        self.connected = False
        print("🔌 MQTT disconnected, trying to reconnect...")
        try:
            # 重连时重新生成密码（可能跨小时）
            client_id, username, password = generate_iotda_mqtt_params(DEVICE_ID, DEVICE_SECRET)
            self.client.username_pw_set(username, password)
            self.client.reconnect()
        except Exception as e:
            print(f"Reconnect error: {e}")

    def send_command(self, led_on):
        """发送指令到自定义 Topic，触发平台规则转发"""
        request_id = str(int(time.time()))
        # 自定义 Topic，必须以 /phone/cmd 开头，符合规则过滤条件
        topic = f"/phone/cmd/led/request_id={request_id}"
        
        # 简单命令格式，不需要 service_id 等包装
        payload = json.dumps({
            "led_ctrl": led_on
        })
        
        result = self.client.publish(topic, payload)
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print(f"📤 Command sent to {topic}: {payload}")
        else:
            print(f"❌ Publish failed, rc: {result.rc}")

class IoTApp(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.mqtt_client = MQTTClient()
        Clock.schedule_interval(self.update_ui, 1)

    def build(self):
        # 设置窗口背景色为浅灰
        Window.clearcolor = (0.95, 0.95, 0.95, 1)
        
        # 主布局
        layout = BoxLayout(orientation='vertical', padding=30, spacing=30)
        
        # 标题
        title = Label(
            text="[b]IoT Servo Controller[/b]",
            markup=True,
            font_size='24sp',
            size_hint_y=0.15,
            color=(0.2, 0.2, 0.2, 1)
        )
        layout.add_widget(title)
        
        # 状态卡片（带背景色）
        self.status_label = Label(
            text="Connecting...",
            font_size='18sp',
            size_hint_y=0.15,
            color=(1, 1, 1, 1),
            halign='center',
            valign='middle'
        )
        # 绑定背景更新
        self.status_label.bind(size=self._update_status_bg, pos=self._update_status_bg)
        layout.add_widget(self.status_label)
        
        # 按钮区域
        btn_layout = BoxLayout(
            orientation='horizontal',
            size_hint_y=0.4,
            spacing=30,
            padding=[50, 0]
        )
        
        self.btn_on = Button(
            text="TURN ON",
            font_size='20sp',
            background_normal='',
            background_color=(0.2, 0.7, 0.3, 1),  # 绿色
            color=(1, 1, 1, 1),
            bold=True
        )
        self.btn_off = Button(
            text="TURN OFF",
            font_size='20sp',
            background_normal='',
            background_color=(0.9, 0.3, 0.3, 1),  # 红色
            color=(1, 1, 1, 1),
            bold=True
        )
        
        self.btn_on.bind(on_press=self.send_on_command)
        self.btn_off.bind(on_press=self.send_off_command)
        
        btn_layout.add_widget(self.btn_on)
        btn_layout.add_widget(self.btn_off)
        layout.add_widget(btn_layout)
        
        # 底部说明（可选）
        footer = Label(
            text="Press button to control servo",
            font_size='14sp',
            size_hint_y=0.15,
            color=(0.5, 0.5, 0.5, 1)
        )
        layout.add_widget(footer)
        
        return layout

    def _update_status_bg(self, instance, value):
        """更新状态标签背景色（连接状态）"""
        instance.canvas.before.clear()
        with instance.canvas.before:
            if self.mqtt_client.connected:
                Color(0.2, 0.7, 0.3, 1)  # 绿色背景
            else:
                Color(0.9, 0.3, 0.3, 1)  # 红色背景
            Rectangle(pos=instance.pos, size=instance.size)

    def send_on_command(self, instance):
        self.mqtt_client.send_command(True)
        self.status_label.text = "Command: ON sent"

    def send_off_command(self, instance):
        self.mqtt_client.send_command(False)
        self.status_label.text = "Command: OFF sent"

    def update_ui(self, dt):
        if self.mqtt_client.connected:
            self.status_label.text = "Status: Connected"
        else:
            self.status_label.text = "Status: Disconnected, reconnecting..."
        # 强制刷新状态标签背景
        self._update_status_bg(self.status_label, None)

    def on_stop(self):
        self.mqtt_client.client.loop_stop()
        self.mqtt_client.client.disconnect()
        print("App closed")

if __name__ == '__main__':
    IoTApp().run()
import threading
import time

try:
    from Adafruit_IO import MQTTClient
except Exception:  # pragma: no cover - optional in local setups
    MQTTClient = None

from config.adafruit_config import (
    ADAFRUIT_IO_KEY,
    ADAFRUIT_IO_USERNAME,
    DEVICE_REGISTRY,
    validate_adafruit_env,
)

class DevicePublisher:
    def __init__(self):
        self.mock_mode = MQTTClient is None
        if not self.mock_mode:
            try:
                validate_adafruit_env()
            except Exception:
                self.mock_mode = True

        self.client = None
        self.connected = False
        self._lock = threading.Lock()

        if not self.mock_mode:
            self.client = MQTTClient(ADAFRUIT_IO_USERNAME, ADAFRUIT_IO_KEY)
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message

    def _on_connect(self, client):
        print('[MQTT] Connected to Adafruit IO')
        self.connected = True

    def _on_disconnect(self, client):
        print('[MQTT] Disconnected from Adafruit IO')
        self.connected = False

    def _on_message(self, client, feed_id, payload):
        print(f'[MQTT] Feed: {feed_id} | Payload: {payload}')

    def connect(self):
        if self.mock_mode:
            self.connected = True
            return

        with self._lock:
            if self.connected:
                return

            self.client.connect()
            self.client.loop_background()

            timeout = time.time() + 5
            while not self.connected and time.time() < timeout:
                time.sleep(0.1)

            if not self.connected:
                raise TimeoutError('Khong the ket noi toi Adafruit IO')

    def disconnect(self):
        with self._lock:
            try:
                if self.client:
                    self.client.disconnect()
            finally:
                self.connected = False

    def publish_raw(self, feed_key: str, value: str):
        if not feed_key:
            raise ValueError('feed_key khong hop le')

        if self.mock_mode:
            print(f'[MOCK MQTT] {feed_key}: {value}')
            return {'success': True, 'feed': feed_key, 'value': value, 'mock': True}

        self.connect()
        self.client.publish(feed_key, value)
        print(f'[MQTT] Published -> {feed_key}: {value}')
        return {'success': True, 'feed': feed_key, 'value': value, 'mock': False}

    def control_device(self, device_name: str, state):
        device_key = str(device_name or '').strip().lower()
        if device_key not in DEVICE_REGISTRY:
            raise ValueError(
                f"Thiet bi '{device_name}' khong ton tai. "
                f"Thiet bi hop le: {list(DEVICE_REGISTRY.keys())}"
            )

        registry = DEVICE_REGISTRY[device_key]
        feed_key = registry.get('feed')
        payload = self._normalize_device_state(device_key, state)
        return self.publish_raw(str(feed_key), payload)

    @staticmethod
    def _normalize_device_state(device_name: str, state):
        registry = DEVICE_REGISTRY.get(device_name, {})
        commands = registry.get('commands') or {}
        state_raw = '' if state is None else str(state).strip()
        state_str = state_raw.lower()

        if state_str in commands:
            return str(commands[state_str])

        if device_name in {'fan_kitchen', 'fan_bedroom'}:
            try:
                numeric_value = max(0, min(100, int(float(state_str))))
                return str(numeric_value)
            except ValueError as exc:
                raise ValueError(
                    f"{device_name} chi nhan on/off hoac so tu 0 den 100"
                ) from exc

        if device_name in {'light_living', 'light_bed'}:
            try:
                numeric_value = max(0, min(100, int(float(state_str))))
                return str(numeric_value)
            except ValueError as exc:
                raise ValueError(
                    f"{device_name} chi nhan on/off hoac do sang tu 0 den 100"
                ) from exc

        if device_name == 'lcd_living':
            if not state_raw:
                raise ValueError('lcd_living can a non-empty message')
            return state_raw

        if commands:
            raise ValueError(
                f"Thiet bi '{device_name}' chi nhan: {sorted(commands.keys())}"
            )

        return state_raw


publisher = DevicePublisher()

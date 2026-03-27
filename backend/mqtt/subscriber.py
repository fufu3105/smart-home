import os
import sys
import threading
import time

try:
    from Adafruit_IO import Client as RestClient
except Exception:  # pragma: no cover - optional bootstrap helper
    RestClient = None

try:
    from Adafruit_IO import MQTTClient
    from Adafruit_IO.errors import MQTTError
except Exception:  # pragma: no cover - optional in local setups
    MQTTClient = None

    class MQTTError(Exception):
        pass

from config.adafruit_config import ADAFRUIT_IO_KEY, ADAFRUIT_IO_USERNAME, DEVICE_REGISTRY, validate_adafruit_env
from database import crud


def _pick_feed(*env_names: str, default: str | None = None) -> str | None:
    for env_name in env_names:
        value = os.getenv(env_name)
        if value and str(value).strip():
            return str(value).strip()
    return default


SENSOR_FEEDS = {
    "temperature": _pick_feed("FEED_TEMPERATURE", "MQTT_FEED_TEMPERATURE", default="nhietdo"),
    "brightness": _pick_feed("FEED_BRIGHTNESS", "MQTT_FEED_BRIGHTNESS", default="brightness"),
    "humidity": _pick_feed("FEED_HUMIDITY", "MQTT_FEED_HUMIDITY"),
    "gas_level": _pick_feed("FEED_GAS", "MQTT_FEED_GAS"),
}

PERSISTED_SENSOR_FIELDS = {"temperature", "humidity", "gas_level"}
DEVICE_STATUS_FEEDS = {}

for device_key, device_meta in DEVICE_REGISTRY.items():
    feed = str(device_meta.get("feed") or "").strip()
    if not feed or feed in DEVICE_STATUS_FEEDS:
        continue
    DEVICE_STATUS_FEEDS[feed] = device_key


_subscriber_thread = None


class SmartHomeSubscriber:
    def __init__(self):
        if MQTTClient is None:
            raise RuntimeError("Thieu package Adafruit_IO de dong bo MQTT.")

        validate_adafruit_env()
        self.client = MQTTClient(ADAFRUIT_IO_USERNAME, ADAFRUIT_IO_KEY)
        self.client.on_connect = self.connected
        self.client.on_disconnect = self.disconnected
        self.client.on_subscribe = self.subscribed
        self.client.on_message = self.message

        self.rest_client = RestClient(ADAFRUIT_IO_USERNAME, ADAFRUIT_IO_KEY) if RestClient else None
        self.device_feed_to_key = dict(DEVICE_STATUS_FEEDS)
        self.sensor_feed_to_field = {
            feed: field
            for field, feed in SENSOR_FEEDS.items()
            if feed and feed not in self.device_feed_to_key
        }
        self.latest_values = {}

    def connected(self, client):
        print("Connected to Adafruit IO!")
        subscribed_feeds = set()

        for field, feed in SENSOR_FEEDS.items():
            if not feed:
                print(f"Skip sensor field={field} vi chua co feed key.")
                continue
            if feed in subscribed_feeds:
                continue
            self.client.subscribe(feed)
            subscribed_feeds.add(feed)
            print(f"Subscribed sensor -> field={field}, feed={feed}")

        for feed, device_key in self.device_feed_to_key.items():
            if feed in subscribed_feeds:
                continue
            self.client.subscribe(feed)
            subscribed_feeds.add(feed)
            print(f"Subscribed device -> device={device_key}, feed={feed}")

    def disconnected(self, client):
        print("Mat ket noi Adafruit IO.")
        sys.exit(1)

    def subscribed(self, client, userdata, mid, granted_qos):
        print("Subscribe thanh cong.")

    def _persist_sensor_value(self, field: str, value: float):
        if field not in PERSISTED_SENSOR_FIELDS:
            return
        crud.insert_sensor_reading(field, value)
        print(f"Da luu sensor_data -> {field}={value}")

    def _persist_device_state(self, device_key: str, payload, source: str):
        device_state = crud.apply_device_command_state(device_key, payload)
        if source == "MQTT":
            crud.insert_device_log(
                device_name=device_key,
                action="mqtt_sync",
                status="success",
                action_source="mqtt",
                action_value=str(payload),
            )
        print(f"Da dong bo device_state -> {device_key}: {device_state['state']}")

    def _handle_payload(self, field: str, feed_id: str, payload, source: str):
        try:
            value = float(payload)
        except (TypeError, ValueError):
            print(f"Payload khong phai so -> feed={feed_id}, payload={payload}")
            return

        self.latest_values[field] = value
        print(f"[{source}] {field} <- {value}")

        try:
            self._persist_sensor_value(field, value)
        except Exception as exc:
            print(f"Loi khi luu DB cho {field}: {exc}")

    def bootstrap_latest_values(self):
        if not self.rest_client:
            return

        all_feeds = set(self.sensor_feed_to_field.keys()) | set(self.device_feed_to_key.keys())

        for feed in all_feeds:
            try:
                data = self.rest_client.receive(feed)
            except Exception as exc:
                print(f"Khong lay duoc gia tri gan nhat cua {feed}: {exc}")
                continue

            payload = getattr(data, "value", None)
            if payload in (None, ""):
                continue

            if feed in self.sensor_feed_to_field:
                self._handle_payload(self.sensor_feed_to_field[feed], feed, payload, source="BOOTSTRAP")

            device_key = self.device_feed_to_key.get(feed)
            if device_key:
                try:
                    self._persist_device_state(device_key, payload, source="BOOTSTRAP")
                except Exception as exc:
                    print(f"Loi khi dong bo device {device_key} tu {feed}: {exc}")

    def message(self, client, feed_id, payload):
        print(f"[MQTT] Subscriber -> {feed_id}: {payload}")

        handled = False

        device_key = self.device_feed_to_key.get(feed_id)
        if device_key:
            handled = True
            try:
                self._persist_device_state(device_key, payload, source="MQTT")
            except Exception as exc:
                print(f"Loi khi dong bo device {device_key} tu {feed_id}: {exc}")

        field = self.sensor_feed_to_field.get(feed_id)
        if field:
            handled = True
            self._handle_payload(field, feed_id, payload, source="MQTT")

        if not handled:
            print(f"Bo qua feed khong xac dinh: {feed_id}")

    def connect(self):
        self.client.connect()
        time.sleep(1)
        self.bootstrap_latest_values()

    def disconnect(self):
        try:
            self.client.disconnect()
        except Exception:
            pass

    def listen(self):
        print("Dang lang nghe du lieu cam bien...")
        try:
            self.client.loop_blocking()
        except MQTTError as exc:
            raise RuntimeError(
                "Adafruit IO tu choi ket noi. "
                "Hay kiem tra ADAFRUIT_IO_USERNAME va ADAFRUIT_IO_KEY trong backend/.env."
            ) from exc


def main():
    sub = SmartHomeSubscriber()
    sub.connect()

    try:
        sub.listen()
    except KeyboardInterrupt:
        print("\nDa dung subscriber.")
    finally:
        sub.disconnect()


if __name__ == "__main__":
    main()


def _subscriber_worker():
    sub = None
    try:
        sub = SmartHomeSubscriber()
        sub.connect()
        sub.listen()
    except Exception as exc:
        print(f"[MQTT] Background subscriber stopped: {exc}")
    finally:
        if sub is not None:
            sub.disconnect()


def start_background_subscriber() -> bool:
    global _subscriber_thread

    if _subscriber_thread and _subscriber_thread.is_alive():
        return True

    if MQTTClient is None:
        print("[MQTT] Background subscriber skipped: Adafruit_IO package unavailable.")
        return False

    try:
        validate_adafruit_env()
    except Exception as exc:
        print(f"[MQTT] Background subscriber skipped: {exc}")
        return False

    thread = threading.Thread(
        target=_subscriber_worker,
        name="smart-home-mqtt-subscriber",
        daemon=True,
    )
    thread.start()
    _subscriber_thread = thread
    print("[MQTT] Background subscriber started.")
    return True

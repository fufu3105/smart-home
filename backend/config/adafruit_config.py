from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional in local setups
    def load_dotenv(*_args, **_kwargs):
        return False

ENV_FILE = Path(__file__).resolve().parents[1] / '.env'
load_dotenv(ENV_FILE, override=True)


ADAFRUIT_IO_USERNAME = os.getenv("ADAFRUIT_IO_USERNAME", "").strip()
ADAFRUIT_IO_KEY = os.getenv("ADAFRUIT_IO_KEY", "").strip()
ADAFRUIT_SCENE_FEED = os.getenv("ADAFRUIT_SCENE_FEED", "scene").strip()


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


DEVICE_REGISTRY: Dict[str, Dict[str, object]] = {
    "light_living": {
        "name": "Living Room Light",
        "feed": _clean(os.getenv("FEED_LIGHT_LIVING")) or "indoorled",
        "commands": {"on": "ON", "off": "OFF"},
    },
    "alarm_living": {
        "name": "Living Room Alarm",
        "feed": _clean(os.getenv("FEED_ALARM_LIVING")) or "alarm",
        "commands": {"on": "1", "off": "0", "1": "1", "0": "0"},
    },
    "door_main": {
        "name": "Main Door",
        "feed": _clean(os.getenv("FEED_DOOR_MAIN")) or "doorlock",
        "commands": {
            "lock": "0",
            "unlock": "1",
            "open": "1",
            "close": "0",
            "1": "1",
            "0": "0",
        },
    },
    "fan_kitchen": {
        "name": "Kitchen Fan",
        "feed": _clean(os.getenv("FEED_FAN_KITCHEN")) or _clean(os.getenv("FEED_FAN_BEDROOM")) or "fan",
        "commands": {"on": "1", "off": "0", "1": "1", "0": "0"},
    },
    "fan_bedroom": {
        "name": "Bedroom Fan",
        "feed": _clean(os.getenv("FEED_FAN_BEDROOM")) or _clean(os.getenv("FEED_FAN_KITCHEN")) or "fan",
        "commands": {"on": "1", "off": "0", "1": "1", "0": "0"},
    },
    "lcd_living": {
        "name": "LCD Display",
        "feed": _clean(os.getenv("FEED_LCD_LIVING")) or "lcd",
        "commands": {},
    },
    "light_bed": {
        "name": "Bedroom Light",
        "feed": _clean(os.getenv("FEED_LIGHT_BED")) or _clean(os.getenv("FEED_LIGHT_BEDROOM")) or "bedled",
        "commands": {"on": "ON", "off": "OFF"},
    },
}


# Only Sleep Mode behavior is explicitly exemplified in the PDF
# (lights off, door locked, alarm on). The Home/Away/Party defaults below
# are backend defaults inferred from the scene names and can be edited later.
SCENE_REGISTRY: Dict[str, Dict[str, object]] = {
    "home_mode": {
        "name": "Home Mode",
        "payload": "home_mode",
        "description": "Welcome home scene",
        "actions": [
            {"device_key": "door_main", "command": "unlock", "execution_order": 1},
            {"device_key": "alarm_living", "command": "off", "execution_order": 2},
            {"device_key": "light_living", "command": "on", "execution_order": 3},
        ],
    },
    "sleep_mode": {
        "name": "Sleep Mode",
        "payload": "sleep_mode",
        "description": "Night routine: lights off, fan low speed, door locked, alarm on",
        "actions": [
            {"device_key": "light_living", "command": "off", "execution_order": 1},
            {"device_key": "light_bed", "command": "off", "execution_order": 2},
            {"device_key": "fan_kitchen", "command": "30", "execution_order": 3},
            {"device_key": "door_main", "command": "lock", "execution_order": 4},
            {"device_key": "alarm_living", "command": "on", "execution_order": 5},
        ],
    },
    "away_mode": {
        "name": "Away Mode",
        "payload": "away_mode",
        "description": "Security mode: lock door, arm alarm, turn lights off",
        "actions": [
            {"device_key": "light_living", "command": "off", "execution_order": 1},
            {"device_key": "light_bed", "command": "off", "execution_order": 2},
            {"device_key": "fan_kitchen", "command": "off", "execution_order": 3},
            {"device_key": "door_main", "command": "lock", "execution_order": 4},
            {"device_key": "alarm_living", "command": "on", "execution_order": 5},
        ],
    },
    "party_mode": {
        "name": "Party Mode",
        "payload": "party_mode",
        "description": "Party scene: lights on, fan high speed, LCD message, alarm off",
        "actions": [
            {"device_key": "door_main", "command": "unlock", "execution_order": 1},
            {"device_key": "alarm_living", "command": "off", "execution_order": 2},
            {"device_key": "light_living", "command": "on", "execution_order": 3},
            {"device_key": "light_bed", "command": "on", "execution_order": 4},
            {"device_key": "fan_kitchen", "command": "80", "execution_order": 5},
            {"device_key": "lcd_living", "command": "PARTY!", "execution_order": 6},
        ],
    },
}


def validate_adafruit_env(require_keys: bool = True) -> None:
    missing: List[str] = []
    if require_keys:
        if not ADAFRUIT_IO_USERNAME:
            missing.append("ADAFRUIT_IO_USERNAME")
        if not ADAFRUIT_IO_KEY:
            missing.append("ADAFRUIT_IO_KEY")
    if missing:
        raise ValueError(f"Thiếu biến môi trường: {', '.join(missing)}")


__all__ = [
    "ADAFRUIT_IO_USERNAME",
    "ADAFRUIT_IO_KEY",
    "ADAFRUIT_SCENE_FEED",
    "DEVICE_REGISTRY",
    "SCENE_REGISTRY",
    "validate_adafruit_env",
]

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from werkzeug.security import generate_password_hash

from config.adafruit_config import DEVICE_REGISTRY, SCENE_REGISTRY
from config.db_config import get_cursor


ROOM_REGISTRY = {
    'living': {'room_name': 'Living Room', 'room_type': 'living'},
    'kitchen': {'room_name': 'Kitchen', 'room_type': 'kitchen'},
    'entrance': {'room_name': 'Entrance', 'room_type': 'entrance'},
    'bedroom': {'room_name': 'Bedroom', 'room_type': 'bedroom'},
    'utility': {'room_name': 'Utility', 'room_type': 'system'},
}

DEVICE_BOOTSTRAP = {
    'light_living': {'room': 'living', 'type': 'light'},
    'lcd_living': {'room': 'living', 'type': 'display'},
    'alarm_living': {'room': 'living', 'type': 'alarm'},
    'fan_kitchen': {'room': 'kitchen', 'type': 'fan'},
    'door_main': {'room': 'entrance', 'type': 'lock'},
    'light_bed': {'room': 'bedroom', 'type': 'light'},
    'sensor_temperature': {'room': 'bedroom', 'type': 'sensor'},
    'sensor_humidity': {'room': 'bedroom', 'type': 'sensor'},
    'sensor_air_quality': {'room': 'kitchen', 'type': 'sensor'},
}

SENSOR_DEVICE_BY_READING = {
    'temperature': 'sensor_temperature',
    'humidity': 'sensor_humidity',
    'gas_level': 'sensor_air_quality',
}

DEFAULT_DEVICE_STATES = {
    'light_living': {'power': 'off', 'level': '0'},
    'lcd_living': {'power': 'off', 'message': ''},
    'alarm_living': {'power': 'off'},
    'fan_kitchen': {'power': 'off', 'speed': '0'},
    'door_main': {'lock': 'locked'},
    'light_bed': {'power': 'off', 'level': '0'},
}


# Alias support for old/new naming mismatches.
DEVICE_ALIASES = {
    'fan_bedroom': 'fan_kitchen',
    'bedroom_light': 'light_bed',
    'living_room_light': 'light_living',
    'main_door': 'door_main',
}


def normalize_device_code(device_code: str) -> str:
    code = (device_code or '').strip().lower()
    return DEVICE_ALIASES.get(code, code)


def scene_key_from_name(scene_name: str) -> str:
    raw = (scene_name or '').strip().lower()
    raw = re.sub(r'[^a-z0-9]+', '_', raw)
    return raw.strip('_')


def _fmt_ts(dt: Optional[datetime] = None) -> str:
    return (dt or datetime.utcnow()).strftime('%Y-%m-%d %H:%M:%S')


def _status_to_result(status: str) -> str:
    normalized = (status or 'pending').strip().lower()
    if normalized in {'ok', 'success', 'sent'}:
        return 'success'
    if normalized in {'failed', 'error'}:
        return 'failed'
    return 'pending'


def _ensure_room(room_key: str) -> int:
    room_info = ROOM_REGISTRY[room_key]
    with get_cursor() as (_conn, cur):
        cur.execute(
            '''
            INSERT INTO rooms (room_name, room_type)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE room_type = VALUES(room_type)
            ''',
            (room_info['room_name'], room_info['room_type']),
        )
        cur.execute('SELECT id FROM rooms WHERE room_name = %s LIMIT 1', (room_info['room_name'],))
        row = cur.fetchone()
        return int(row[0])


def _ensure_device(device_code: str) -> int:
    device_code = normalize_device_code(device_code)
    if device_code not in DEVICE_BOOTSTRAP:
        raise ValueError(f'Unknown device_code: {device_code}')

    bootstrap = DEVICE_BOOTSTRAP[device_code]
    room_id = _ensure_room(bootstrap['room'])

    registry = DEVICE_REGISTRY.get(device_code, {})
    device_name = registry.get('name') or device_code.replace('_', ' ').title()
    mqtt_topic_command = registry.get('feed')
    mqtt_topic_status = registry.get('feed')

    with get_cursor() as (_conn, cur):
        cur.execute(
            '''
            INSERT INTO devices (
                room_id, created_by_user_id, device_code, device_type,
                device_name, mqtt_topic_status, mqtt_topic_command, is_active
            )
            VALUES (%s, NULL, %s, %s, %s, %s, %s, TRUE)
            ON DUPLICATE KEY UPDATE
                room_id = VALUES(room_id),
                device_type = VALUES(device_type),
                device_name = VALUES(device_name),
                mqtt_topic_status = VALUES(mqtt_topic_status),
                mqtt_topic_command = VALUES(mqtt_topic_command),
                is_active = TRUE
            ''',
            (
                room_id,
                device_code,
                bootstrap['type'],
                device_name,
                mqtt_topic_status,
                mqtt_topic_command,
            ),
        )
        cur.execute('SELECT id FROM devices WHERE device_code = %s LIMIT 1', (device_code,))
        row = cur.fetchone()
        return int(row[0])


def _get_user_id_by_username(username: str = 'admin') -> Optional[int]:
    with get_cursor() as (_conn, cur):
        cur.execute('SELECT id FROM users WHERE LOWER(username) = LOWER(%s) LIMIT 1', (username,))
        row = cur.fetchone()
        return int(row[0]) if row else None


def resolve_existing_user_id(user_id: Optional[Any]) -> Optional[int]:
    if user_id is None or str(user_id).strip() == '':
        return None

    try:
        normalized = int(user_id)
    except (TypeError, ValueError):
        return None

    with get_cursor() as (_conn, cur):
        cur.execute('SELECT id FROM users WHERE id = %s LIMIT 1', (normalized,))
        row = cur.fetchone()
        return int(row[0]) if row else None


def _get_device_id(device_code: str) -> int:
    code = normalize_device_code(device_code)
    with get_cursor() as (_conn, cur):
        cur.execute('SELECT id FROM devices WHERE device_code = %s LIMIT 1', (code,))
        row = cur.fetchone()
        if row:
            return int(row[0])
    return _ensure_device(code)


def _device_kind(device_code: str) -> str:
    code = normalize_device_code(device_code)
    return str(DEVICE_BOOTSTRAP.get(code, {}).get('type') or 'device')


def _get_latest_device_state_value(device_code: str, state_key: str) -> Optional[str]:
    code = normalize_device_code(device_code)
    device_id = _get_device_id(code)
    with get_cursor() as (_conn, cur):
        cur.execute(
            '''
            SELECT state_value
            FROM device_states
            WHERE device_id = %s AND state_key = %s
            ORDER BY recorded_at DESC
            LIMIT 1
            ''',
            (device_id, state_key),
        )
        row = cur.fetchone()
        return str(row[0]) if row and row[0] is not None else None


def _normalize_device_command_state(device_code: str, command: Any) -> Dict[str, Any]:
    code = normalize_device_code(device_code)
    kind = _device_kind(code)
    raw = '' if command is None else str(command).strip()
    lowered = raw.lower()

    if code == 'door_main' or kind == 'lock':
        unlocked = lowered in {'1', 'on', 'open', 'unlock', 'unlocked', 'true'}
        state = {'lock': 'unlocked' if unlocked else 'locked'}
        return {
            'device_key': code,
            'kind': kind,
            'is_on': unlocked,
            'state': state,
            'entries': list(state.items()),
        }

    if kind == 'fan':
        if lowered in {'', 'off', '0', 'false', 'stop'}:
            speed = 0
        elif lowered in {'on', '1', 'true'}:
            speed = 100
        else:
            speed = max(0, min(100, int(float(raw))))
        state = {'power': 'on' if speed > 0 else 'off', 'speed': str(speed)}
        return {
            'device_key': code,
            'kind': kind,
            'is_on': speed > 0,
            'state': state,
            'entries': list(state.items()),
        }

    if kind == 'display':
        power = 'off' if lowered in {'', 'off', '0', 'false'} else 'on'
        message = '' if power == 'off' else raw
        state = {'power': power, 'message': message}
        return {
            'device_key': code,
            'kind': kind,
            'is_on': power == 'on',
            'state': state,
            'entries': list(state.items()),
        }

    if kind == 'light':
        if lowered in {'', 'off', '0', 'false'}:
            level = 0
            power = 'off'
        elif lowered in {'on', '1', 'true'}:
            remembered_level = _get_latest_device_state_value(code, 'level')
            try:
                level = max(0, min(100, int(float(remembered_level or '100'))))
            except (TypeError, ValueError):
                level = 100
            if level == 0:
                level = 100
            power = 'on'
        else:
            try:
                level = max(0, min(100, int(float(raw))))
                power = 'on' if level > 0 else 'off'
            except (TypeError, ValueError):
                level = 0
                power = 'off'
        state = {'power': power, 'level': str(level)}
        return {
            'device_key': code,
            'kind': kind,
            'is_on': power == 'on',
            'state': state,
            'entries': list(state.items()),
        }

    power = 'on' if lowered in {'on', '1', 'true', 'armed'} else 'off'
    state = {'power': power}
    return {
        'device_key': code,
        'kind': kind,
        'is_on': power == 'on',
        'state': state,
        'entries': list(state.items()),
    }


def ensure_tables(conn=None) -> None:
    # Schema is expected to be created separately in MySQL from schema.sql.
    # This function only ensures reference/bootstrap data.
    ensure_reference_data()
    ensure_default_scenes()
    ensure_default_device_states()


def ensure_reference_data() -> None:
    for room_key in ROOM_REGISTRY:
        _ensure_room(room_key)
    for device_code in DEVICE_BOOTSTRAP:
        _ensure_device(device_code)


def ensure_default_scenes(created_by_username: str = 'admin') -> None:
    ensure_reference_data()
    creator_id = _get_user_id_by_username(created_by_username)
    if creator_id is None:
        return

    with get_cursor() as (_conn, cur):
        for scene_key, scene_meta in SCENE_REGISTRY.items():
            scene_name = str(scene_meta['name'])
            description = scene_meta.get('description')
            trigger_type = 'manual'
            cur.execute(
                '''
                SELECT id FROM scenes
                WHERE created_by_user_id = %s AND LOWER(scene_name) = LOWER(%s)
                LIMIT 1
                ''',
                (creator_id, scene_name),
            )
            row = cur.fetchone()
            if row:
                scene_id = int(row[0])
                cur.execute(
                    '''
                    UPDATE scenes
                    SET description = %s,
                        trigger_type = %s,
                        is_active = TRUE
                    WHERE id = %s
                    ''',
                    (description, trigger_type, scene_id),
                )
            else:
                cur.execute(
                    '''
                    INSERT INTO scenes (created_by_user_id, scene_name, description, trigger_type, is_active)
                    VALUES (%s, %s, %s, %s, TRUE)
                    ''',
                    (creator_id, scene_name, description, trigger_type),
                )
                scene_id = int(cur.lastrowid)

            cur.execute('DELETE FROM scene_devices WHERE scene_id = %s', (scene_id,))
            for item in scene_meta.get('actions', []):
                device_id = _get_device_id(str(item['device_key']))
                cur.execute(
                    '''
                    INSERT INTO scene_devices (scene_id, device_id, action_name, action_value, execution_order)
                    VALUES (%s, %s, %s, %s, %s)
                    ''',
                    (
                        scene_id,
                        device_id,
                        'set_state',
                        str(item['command']),
                        int(item.get('execution_order', 1)),
                    ),
                )


def record_device_state(
    device_code: str,
    state_key: str,
    state_value: Any,
    timestamp: Optional[str] = None,
) -> None:
    ensure_reference_data()
    device_id = _get_device_id(device_code)
    with get_cursor() as (_conn, cur):
        cur.execute(
            '''
            INSERT INTO device_states (device_id, state_key, state_value, recorded_at)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE state_value = VALUES(state_value)
            ''',
            (device_id, str(state_key), '' if state_value is None else str(state_value), timestamp or _fmt_ts()),
        )


def ensure_default_device_states() -> None:
    ensure_reference_data()
    with get_cursor() as (_conn, cur):
        cur.execute('SELECT COUNT(*) FROM device_states')
        count = int(cur.fetchone()[0] or 0)
    if count > 0:
        return

    for device_code, states in DEFAULT_DEVICE_STATES.items():
        for state_key, state_value in states.items():
            record_device_state(device_code, state_key, state_value)


def apply_device_command_state(device_code: str, command: Any, timestamp: Optional[str] = None) -> Dict[str, Any]:
    normalized = _normalize_device_command_state(device_code, command)
    for state_key, state_value in normalized['entries']:
        record_device_state(normalized['device_key'], state_key, state_value, timestamp=timestamp)
    return {
        'device_key': normalized['device_key'],
        'kind': normalized['kind'],
        'is_on': normalized['is_on'],
        'state': normalized['state'],
    }


def seed_sample_data() -> None:
    ensure_reference_data()
    with get_cursor() as (_conn, cur):
        cur.execute('SELECT COUNT(*) FROM users')
        user_count = int(cur.fetchone()[0] or 0)
        if user_count == 0:
            users = [
                ('admin', 'Administrator', 'admin@example.com', generate_password_hash('adminpass'), 'admin', 'active'),
                ('alice', 'Alice Nguyen', 'alice@example.com', generate_password_hash('alicepass'), 'resident', 'active'),
                ('bob', 'Bob Tran', 'bob@example.com', generate_password_hash('bobpass'), 'resident', 'active'),
            ]
            cur.executemany(
                '''
                INSERT INTO users (username, full_name, email, password_hash, role, status)
                VALUES (%s, %s, %s, %s, %s, %s)
                ''',
                users,
            )

    ensure_default_scenes()
    ensure_default_device_states()

    if get_max_sensor_id() == 0:
        now = datetime.utcnow()
        for i in range(30):
            ts = now - timedelta(minutes=i)
            insert_sensor_data(
                temperature=24.0 + (i % 5) * 0.4,
                humidity=48.0 + (i % 7) * 1.2,
                gas_level=110.0 + (i % 4) * 10,
                timestamp=_fmt_ts(ts),
            )
    if get_max_log_id() == 0:
        insert_device_log('light_living', 'bootstrap on', 'success')
        insert_device_log('fan_kitchen', 'bootstrap auto', 'pending')


def add_user(username: str, full_name: str, role: str = 'resident', password: str = '123456', email: Optional[str] = None) -> None:
    with get_cursor() as (_conn, cur):
        cur.execute(
            '''
            INSERT INTO users (username, full_name, email, password_hash, role, status)
            VALUES (%s, %s, %s, %s, %s, 'active')
            ''',
            (username, full_name, email, generate_password_hash(password), role),
        )


def set_user_password(username: str, password_hash: str) -> None:
    with get_cursor() as (_conn, cur):
        cur.execute(
            'UPDATE users SET password_hash = %s WHERE LOWER(username) = LOWER(%s)',
            (password_hash, username),
        )


def fetch_users() -> List[Tuple]:
    with get_cursor() as (_conn, cur):
        cur.execute(
            '''
            SELECT id, username, full_name, role, created_at
            FROM users
            ORDER BY id ASC
            '''
        )
        return cur.fetchall()


def fetch_user_by_username(username: str):
    with get_cursor() as (_conn, cur):
        cur.execute(
            '''
            SELECT id, username, full_name, password_hash, role, created_at
            FROM users
            WHERE LOWER(username) = LOWER(%s)
            LIMIT 1
            ''',
            (username,),
        )
        return cur.fetchone()


def insert_sensor_data(temperature: float, humidity: float, gas_level: float, timestamp: Optional[str] = None) -> None:
    ensure_reference_data()
    ts = timestamp or _fmt_ts()
    rows = [
        ('temperature', Decimal(str(temperature)), '°C'),
        ('humidity', Decimal(str(humidity)), '%'),
        ('gas_level', Decimal(str(gas_level)), 'ppm'),
    ]

    with get_cursor() as (_conn, cur):
        for reading_type, value_decimal, unit in rows:
            device_code = SENSOR_DEVICE_BY_READING[reading_type]
            cur.execute('SELECT id FROM devices WHERE device_code = %s LIMIT 1', (device_code,))
            row = cur.fetchone()
            if not row:
                raise RuntimeError(f'Device bootstrap missing for {device_code}')
            device_id = int(row[0])
            quality_flag = 'normal'
            if reading_type == 'gas_level' and value_decimal >= 300:
                quality_flag = 'danger'
            elif reading_type in {'temperature', 'humidity'} and value_decimal >= 70:
                quality_flag = 'warning'
            cur.execute(
                '''
                INSERT INTO sensor_readings (device_id, reading_type, value_decimal, unit, quality_flag, recorded_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ''',
                (device_id, reading_type, value_decimal, unit, quality_flag, ts),
            )


def insert_sensor_reading(reading_type: str, value: float, timestamp: Optional[str] = None) -> None:
    ensure_reference_data()

    normalized_type = (reading_type or '').strip().lower()
    if normalized_type not in SENSOR_DEVICE_BY_READING:
        raise ValueError(f'Unsupported reading_type: {reading_type}')

    ts = timestamp or _fmt_ts()
    value_decimal = Decimal(str(value))
    device_code = SENSOR_DEVICE_BY_READING[normalized_type]

    unit_by_type = {
        'temperature': 'Â°C',
        'humidity': '%',
        'gas_level': 'ppm',
    }

    quality_flag = 'normal'
    if normalized_type == 'gas_level' and value_decimal >= 300:
        quality_flag = 'danger'
    elif normalized_type in {'temperature', 'humidity'} and value_decimal >= 70:
        quality_flag = 'warning'

    with get_cursor() as (_conn, cur):
        cur.execute('SELECT id FROM devices WHERE device_code = %s LIMIT 1', (device_code,))
        row = cur.fetchone()
        if not row:
            raise RuntimeError(f'Device bootstrap missing for {device_code}')

        cur.execute(
            '''
            INSERT INTO sensor_readings (device_id, reading_type, value_decimal, unit, quality_flag, recorded_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ''',
            (
                int(row[0]),
                normalized_type,
                value_decimal,
                unit_by_type[normalized_type],
                quality_flag,
                ts,
            ),
        )


def fetch_latest_sensor_data(limit: int = 60) -> List[Tuple]:
    limit = max(1, int(limit))
    with get_cursor() as (_conn, cur):
        cur.execute(
            '''
            SELECT
                MAX(sr.id) AS synthetic_id,
                sr.recorded_at,
                MAX(CASE WHEN sr.reading_type = 'temperature' THEN sr.value_decimal END) AS temperature,
                MAX(CASE WHEN sr.reading_type = 'humidity' THEN sr.value_decimal END) AS humidity,
                MAX(CASE WHEN sr.reading_type = 'gas_level' THEN sr.value_decimal END) AS gas_level
            FROM sensor_readings sr
            WHERE sr.reading_type IN ('temperature', 'humidity', 'gas_level')
            GROUP BY sr.recorded_at
            ORDER BY sr.recorded_at DESC
            LIMIT %s
            ''',
            (limit,),
        )
        rows = cur.fetchall()
        return [
            (
                int(r[0]),
                r[1].strftime('%Y-%m-%d %H:%M:%S') if hasattr(r[1], 'strftime') else str(r[1]),
                float(r[2]) if r[2] is not None else None,
                float(r[3]) if r[3] is not None else None,
                float(r[4]) if r[4] is not None else None,
            )
            for r in rows
        ]


def insert_device_log(
    device_name: str,
    action: str,
    status: str,
    timestamp: Optional[str] = None,
    triggered_by_user_id: Optional[int] = None,
    triggered_by_scene_id: Optional[int] = None,
    triggered_by_rule_id: Optional[int] = None,
    action_source: Optional[str] = None,
    action_value: Optional[str] = None,
) -> None:
    ensure_reference_data()
    device_id = _ensure_device(device_name)
    safe_user_id = resolve_existing_user_id(triggered_by_user_id)

    allowed_sources = {'manual', 'auto', 'scene', 'ai', 'mqtt'}
    resolved_source = (action_source or 'manual').lower()

    action_lower = (action or '').lower()
    if triggered_by_scene_id:
        resolved_source = 'scene'
    elif 'scene' in action_lower:
        resolved_source = 'scene'
    elif 'mqtt' in action_lower or 'api' in action_lower:
        resolved_source = 'mqtt'

    if resolved_source not in allowed_sources:
        resolved_source = 'manual'

    with get_cursor() as (_conn, cur):
        cur.execute(
            '''
            INSERT INTO device_actions (
                device_id, triggered_by_user_id, triggered_by_scene_id, triggered_by_rule_id,
                action_name, action_value, action_source, result_status, executed_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''',
            (
                device_id,
                safe_user_id,
                triggered_by_scene_id,
                triggered_by_rule_id,
                action,
                action_value if action_value is not None else status,
                resolved_source,
                _status_to_result(status),
                timestamp or _fmt_ts(),
            ),
        )


def fetch_device_logs(limit: int = 100) -> List[Tuple]:
    limit = max(1, int(limit))
    with get_cursor() as (_conn, cur):
        cur.execute(
            '''
            SELECT da.id, da.executed_at, d.device_code, da.action_name, da.result_status
            FROM device_actions da
            INNER JOIN devices d ON d.id = da.device_id
            ORDER BY da.id DESC
            LIMIT %s
            ''',
            (limit,),
        )
        rows = cur.fetchall()
        return [
            (
                int(r[0]),
                r[1].strftime('%Y-%m-%d %H:%M:%S') if hasattr(r[1], 'strftime') else str(r[1]),
                r[2],
                r[3],
                r[4],
            )
            for r in rows
        ]


def get_max_sensor_id() -> int:
    with get_cursor() as (_conn, cur):
        cur.execute('SELECT COALESCE(MAX(id), 0) FROM sensor_readings')
        return int(cur.fetchone()[0] or 0)


def get_max_log_id() -> int:
    with get_cursor() as (_conn, cur):
        cur.execute('SELECT COALESCE(MAX(id), 0) FROM device_actions')
        return int(cur.fetchone()[0] or 0)


def fetch_devices() -> List[Tuple[str, str, str]]:
    ensure_reference_data()
    with get_cursor() as (_conn, cur):
        cur.execute(
            '''
            SELECT d.device_code, d.device_name, r.room_type
            FROM devices d
            INNER JOIN rooms r ON r.id = d.room_id
            WHERE d.device_code IN (%s, %s, %s, %s, %s, %s)
            ORDER BY d.id ASC
            ''',
            ('light_living', 'lcd_living', 'alarm_living', 'fan_kitchen', 'door_main', 'light_bed'),
        )
        return cur.fetchall()


def fetch_devices_with_state() -> List[Dict[str, Any]]:
    ensure_reference_data()
    ensure_default_device_states()
    with get_cursor() as (_conn, cur):
        cur.execute(
            '''
            SELECT
                d.device_code,
                d.device_name,
                d.device_type,
                r.room_type,
                (
                    SELECT ds.state_value
                    FROM device_states ds
                    WHERE ds.device_id = d.id AND ds.state_key = 'power'
                    ORDER BY ds.recorded_at DESC
                    LIMIT 1
                ) AS power_state,
                (
                    SELECT ds.state_value
                    FROM device_states ds
                    WHERE ds.device_id = d.id AND ds.state_key = 'level'
                    ORDER BY ds.recorded_at DESC
                    LIMIT 1
                ) AS level_state,
                (
                    SELECT ds.state_value
                    FROM device_states ds
                    WHERE ds.device_id = d.id AND ds.state_key = 'speed'
                    ORDER BY ds.recorded_at DESC
                    LIMIT 1
                ) AS speed_state,
                (
                    SELECT ds.state_value
                    FROM device_states ds
                    WHERE ds.device_id = d.id AND ds.state_key = 'lock'
                    ORDER BY ds.recorded_at DESC
                    LIMIT 1
                ) AS lock_state,
                (
                    SELECT ds.state_value
                    FROM device_states ds
                    WHERE ds.device_id = d.id AND ds.state_key = 'message'
                    ORDER BY ds.recorded_at DESC
                    LIMIT 1
                ) AS message_state
            FROM devices d
            INNER JOIN rooms r ON r.id = d.room_id
            WHERE d.device_code IN (%s, %s, %s, %s, %s, %s)
            ORDER BY d.id ASC
            ''',
            ('light_living', 'lcd_living', 'alarm_living', 'fan_kitchen', 'door_main', 'light_bed'),
        )
        rows = cur.fetchall()

    devices: List[Dict[str, Any]] = []
    for row in rows:
        device_key = str(row[0])
        device_type = str(row[2])
        state = {}
        if row[4] is not None:
            state['power'] = str(row[4])
        if row[5] is not None:
            state['level'] = str(row[5])
        if row[6] is not None:
            state['speed'] = str(row[6])
        if row[7] is not None:
            state['lock'] = str(row[7])
        if row[8] is not None:
            state['message'] = str(row[8])

        is_on = False
        if device_type == 'lock':
            is_on = state.get('lock') == 'unlocked'
        elif device_type == 'fan':
            try:
                is_on = int(state.get('speed', '0')) > 0
            except ValueError:
                is_on = state.get('power') == 'on'
        else:
            is_on = state.get('power') == 'on'

        devices.append(
            {
                'key': device_key,
                'name': str(row[1]),
                'type': device_type,
                'room': str(row[3]),
                'is_on': is_on,
                'state': state,
            }
        )
    return devices


def insert_activity_log(
    activity_type: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    user_id: Optional[int] = None,
    detail: Optional[Dict[str, Any]] = None,
) -> None:
    safe_user_id = resolve_existing_user_id(user_id)

    with get_cursor() as (_conn, cur):
        cur.execute(
            '''
            INSERT INTO activity_logs (user_id, activity_type, entity_type, entity_id, detail_json)
            VALUES (%s, %s, %s, %s, %s)
            ''',
            (
                safe_user_id,
                activity_type,
                entity_type,
                entity_id,
                json.dumps(detail, ensure_ascii=False) if detail is not None else None,
            ),
        )


def fetch_scenes(active_only: bool = False) -> List[Dict[str, Any]]:
    ensure_default_scenes()
    query = '''
        SELECT s.id, s.scene_name, s.description, s.trigger_type, s.is_active, s.created_at, COUNT(sd.id) AS action_count
        FROM scenes s
        LEFT JOIN scene_devices sd ON sd.scene_id = s.id
    '''
    params: List[Any] = []
    if active_only:
        query += ' WHERE s.is_active = TRUE '
    query += '''
        GROUP BY s.id, s.scene_name, s.description, s.trigger_type, s.is_active, s.created_at
        ORDER BY s.id ASC
    '''
    with get_cursor() as (_conn, cur):
        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        return [
            {
                'id': int(r[0]),
                'scene_key': scene_key_from_name(r[1]),
                'scene_name': r[1],
                'description': r[2],
                'trigger_type': r[3],
                'is_active': bool(r[4]),
                'created_at': r[5].strftime('%Y-%m-%d %H:%M:%S') if hasattr(r[5], 'strftime') else str(r[5]),
                'action_count': int(r[6] or 0),
            }
            for r in rows
        ]


def fetch_scene_detail(scene_key: str) -> Optional[Dict[str, Any]]:
    normalized = scene_key_from_name(scene_key)
    with get_cursor() as (_conn, cur):
        cur.execute(
            '''
            SELECT id, scene_name, description, trigger_type, is_active, created_at
            FROM scenes
            ORDER BY id ASC
            '''
        )
        rows = cur.fetchall()
        target = None
        for r in rows:
            if scene_key_from_name(r[1]) == normalized:
                target = r
                break
        if not target:
            return None
        return {
            'id': int(target[0]),
            'scene_key': normalized,
            'scene_name': target[1],
            'description': target[2],
            'trigger_type': target[3],
            'is_active': bool(target[4]),
            'created_at': target[5].strftime('%Y-%m-%d %H:%M:%S') if hasattr(target[5], 'strftime') else str(target[5]),
            'actions': fetch_scene_actions(normalized),
        }


def fetch_scene_actions(scene_key: str) -> List[Dict[str, Any]]:
    scene = _fetch_scene_row_by_key(scene_key)
    if not scene:
        return []
    scene_id = int(scene[0])
    with get_cursor() as (_conn, cur):
        cur.execute(
            '''
            SELECT d.device_code, d.device_name, sd.action_name, sd.action_value, sd.execution_order
            FROM scene_devices sd
            INNER JOIN devices d ON d.id = sd.device_id
            WHERE sd.scene_id = %s
            ORDER BY sd.execution_order ASC, sd.id ASC
            ''',
            (scene_id,),
        )
        rows = cur.fetchall()
        return [
            {
                'device_key': r[0],
                'device_name': r[1],
                'action_name': r[2],
                'command': r[3],
                'execution_order': int(r[4]),
            }
            for r in rows
        ]


def _fetch_scene_row_by_key(scene_key: str):
    normalized = scene_key_from_name(scene_key)
    with get_cursor() as (_conn, cur):
        cur.execute(
            '''
            SELECT id, scene_name, description, trigger_type, is_active, created_at
            FROM scenes
            ORDER BY id ASC
            '''
        )
        rows = cur.fetchall()
        for r in rows:
            if scene_key_from_name(r[1]) == normalized:
                return r
    return None


def resolve_scene_id(scene_key: str) -> Optional[int]:
    row = _fetch_scene_row_by_key(scene_key)
    return int(row[0]) if row else None


def fetch_scene_history(limit: int = 50) -> List[Dict[str, Any]]:
    limit = max(1, int(limit))
    with get_cursor() as (_conn, cur):
        cur.execute(
            '''
            SELECT al.id, al.created_at, s.scene_name, al.detail_json, u.username
            FROM activity_logs al
            LEFT JOIN scenes s ON s.id = al.entity_id AND al.entity_type = 'scenes'
            LEFT JOIN users u ON u.id = al.user_id
            WHERE al.entity_type = 'scenes' AND al.activity_type = 'scene_activated'
            ORDER BY al.id DESC
            LIMIT %s
            ''',
            (limit,),
        )
        rows = cur.fetchall()
        history = []
        for r in rows:
            detail = None
            if r[3]:
                try:
                    detail = json.loads(r[3]) if isinstance(r[3], str) else r[3]
                except Exception:
                    detail = {'raw': str(r[3])}
            history.append(
                {
                    'id': int(r[0]),
                    'activated_at': r[1].strftime('%Y-%m-%d %H:%M:%S') if hasattr(r[1], 'strftime') else str(r[1]),
                    'scene_name': r[2],
                    'scene_key': scene_key_from_name(r[2] or ''),
                    'activated_by': r[4],
                    'detail': detail,
                }
            )
        return history

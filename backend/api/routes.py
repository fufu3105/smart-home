import json
import time
from typing import Any, Dict, Optional

from flask import Blueprint, Response, current_app, jsonify, request
from itsdangerous import BadSignature, SignatureExpired
from werkzeug.security import check_password_hash

from database import crud
from mqtt.publisher import publisher

try:
    from itsdangerous import TimedJSONWebSignatureSerializer as Serializer

    _HAS_TIMED = True
except Exception:
    from itsdangerous import URLSafeTimedSerializer as Serializer

    _HAS_TIMED = False


api = Blueprint('api', __name__, url_prefix='/api')

FAILED_LOGIN_LIMIT = 3
FAILED_LOGIN_LOCK_SECONDS = 300


def _get_serializer():
    secret = current_app.config.get('SECRET_KEY') or 'dev-secret'
    if _HAS_TIMED:
        return Serializer(secret, expires_in=86400)
    return Serializer(secret)


def _extract_bearer_token() -> Optional[str]:
    auth_header = (request.headers.get('Authorization') or '').strip()
    if not auth_header:
        return None
    parts = auth_header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        return None
    return parts[1].strip() or None


def _get_auth_user(optional: bool = True) -> Optional[Dict[str, Any]]:
    token = _extract_bearer_token()
    if not token:
        if optional:
            return None
        raise PermissionError('Thieu Bearer token')

    serializer = _get_serializer()
    try:
        if _HAS_TIMED:
            data = serializer.loads(token)
        else:
            data = serializer.loads(token, max_age=86400)
    except SignatureExpired as exc:
        raise PermissionError('Token da het han') from exc
    except BadSignature as exc:
        raise PermissionError('Token khong hop le') from exc

    if not isinstance(data, dict):
        if optional:
            return None
        raise PermissionError('Token khong hop le')
    return data


def _get_login_attempt_store() -> Dict[str, Dict[str, Any]]:
    return current_app.config.setdefault('_LOGIN_ATTEMPTS', {})


def _get_login_attempt(username: str) -> Dict[str, Any]:
    store = _get_login_attempt_store()
    key = (username or '').strip().lower()
    if key not in store:
        store[key] = {'count': 0, 'locked_until': 0.0}
    return store[key]


def _clear_failed_login(username: str) -> None:
    store = _get_login_attempt_store()
    store.pop((username or '').strip().lower(), None)


def _record_failed_login(username: str) -> Dict[str, Any]:
    item = _get_login_attempt(username)
    now = time.time()
    if item.get('locked_until', 0.0) > now:
        return item

    item['count'] = int(item.get('count', 0)) + 1
    if item['count'] >= FAILED_LOGIN_LIMIT:
        item['locked_until'] = now + FAILED_LOGIN_LOCK_SECONDS
    return item


def _is_login_locked(username: str) -> Optional[int]:
    item = _get_login_attempt(username)
    remaining = int(item.get('locked_until', 0.0) - time.time())
    return remaining if remaining > 0 else None


@api.route('/health')
def health():
    return jsonify({'status': 'ok'})


@api.route('/users')
def users():
    rows = crud.fetch_users()
    data = [
        {'id': r[0], 'username': r[1], 'full_name': r[2], 'role': r[3], 'created_at': r[4]}
        for r in rows
    ]
    return jsonify(data)


@api.route('/login', methods=['POST'])
def login():
    payload = request.get_json(silent=True) or {}
    username = (payload.get('username') or '').strip()
    password = payload.get('password') or ''

    if not username or not password:
        return jsonify({'error': 'username and password required'}), 400

    locked_seconds = _is_login_locked(username)
    if locked_seconds:
        return (
            jsonify(
                {
                    'error': 'too many failed login attempts',
                    'retry_after_seconds': locked_seconds,
                }
            ),
            429,
        )

    row = crud.fetch_user_by_username(username)
    if not row:
        _record_failed_login(username)
        crud.insert_activity_log(
            activity_type='login_failed',
            entity_type='users',
            detail={'username': username, 'reason': 'user_not_found'},
        )
        return jsonify({'error': 'invalid credentials'}), 401

    user_id, uname, full_name, pw_hash, role, _created_at = row
    valid = False

    if pw_hash:
        try:
            valid = check_password_hash(pw_hash, password)
        except Exception:
            valid = False
        if not valid and pw_hash == password:
            valid = True

    if not valid:
        state = _record_failed_login(username)
        crud.insert_activity_log(
            activity_type='login_failed',
            entity_type='users',
            entity_id=int(user_id),
            detail={
                'username': uname,
                'reason': 'invalid_password',
                'failed_count': int(state.get('count', 0)),
            },
        )
        status_code = 429 if _is_login_locked(username) else 401
        body = {'error': 'invalid credentials'}
        if status_code == 429:
            body = {
                'error': 'too many failed login attempts',
                'retry_after_seconds': _is_login_locked(username),
            }
        return jsonify(body), status_code

    _clear_failed_login(username)

    serializer = _get_serializer()
    token_obj = serializer.dumps({'id': int(user_id), 'username': uname, 'role': role})
    token = token_obj.decode('utf-8') if isinstance(token_obj, (bytes, bytearray)) else token_obj

    crud.insert_activity_log(
        activity_type='user_login',
        entity_type='users',
        entity_id=int(user_id),
        user_id=int(user_id),
        detail={'username': uname, 'role': role},
    )

    return jsonify(
        {
            'status': 'ok',
            'token': token,
            'user': {
                'id': int(user_id),
                'username': uname,
                'full_name': full_name,
                'role': role,
            },
        }
    )


@api.route('/sensor/latest')
def sensor_latest():
    limit = int(request.args.get('limit', 60))
    rows = crud.fetch_latest_sensor_data(limit)
    data = [
        {'id': r[0], 'timestamp': r[1], 'temperature': r[2], 'humidity': r[3], 'gas_level': r[4]}
        for r in rows
    ]
    return jsonify(data)


@api.route('/sensor/history')
def sensor_history():
    limit = int(request.args.get('limit', 200))
    rows = crud.fetch_latest_sensor_data(limit)
    data = [
        {'id': r[0], 'timestamp': r[1], 'temperature': r[2], 'humidity': r[3], 'gas_level': r[4]}
        for r in rows
    ]
    return jsonify(data)


@api.route('/sensor', methods=['POST'])
def post_sensor():
    payload = request.get_json(silent=True) or {}
    try:
        temperature = float(payload.get('temperature'))
        humidity = float(payload.get('humidity'))
        gas_level = float(payload.get('gas_level'))
    except Exception:
        return jsonify({'error': 'invalid payload'}), 400

    crud.insert_sensor_data(temperature, humidity, gas_level)
    return jsonify({'status': 'ok'})


@api.route('/devices')
def devices():
    return jsonify(crud.fetch_devices_with_state())


@api.route('/devices/control', methods=['POST'])
def devices_control():
    payload = request.get_json(silent=True) or {}
    device_key = (payload.get('device_key') or payload.get('device_name') or '').strip()
    command = payload.get('state', payload.get('command', payload.get('value')))

    if not device_key:
        return jsonify({'error': 'device_key is required'}), 400
    if command is None or str(command).strip() == '':
        return jsonify({'error': 'state/command/value is required'}), 400

    user = None
    try:
        user = _get_auth_user(optional=True)
    except PermissionError as exc:
        return jsonify({'error': str(exc)}), 401

    user_id = int(user['id']) if user and user.get('id') is not None else None

    try:
        mqtt_result = publisher.control_device(device_key, command)
        device_state = crud.apply_device_command_state(device_key, command)
        crud.insert_device_log(
            device_name=device_key,
            action='control_device',
            status='success',
            triggered_by_user_id=user_id,
            action_source='api',
            action_value=str(command),
        )
        return jsonify(
            {
                'status': 'ok',
                'device_key': device_key,
                'command': command,
                'mqtt': mqtt_result,
                'device_state': device_state,
            }
        )
    except ValueError as exc:
        crud.insert_device_log(
            device_name=device_key,
            action='control_device',
            status='failed',
            triggered_by_user_id=user_id,
            action_source='api',
            action_value=str(command),
        )
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:
        crud.insert_device_log(
            device_name=device_key,
            action='control_device',
            status='failed',
            triggered_by_user_id=user_id,
            action_source='api',
            action_value=str(command),
        )
        return jsonify({'error': f'Loi dieu khien thiet bi: {exc}'}), 500


@api.route('/scenes', methods=['GET'])
def scenes():
    active_only = str(request.args.get('active_only', '')).strip().lower() in {'1', 'true', 'yes'}
    return jsonify(crud.fetch_scenes(active_only=active_only))


@api.route('/scenes/<scene_key>', methods=['GET'])
def scene_detail(scene_key: str):
    scene = crud.fetch_scene_detail(scene_key)
    if not scene:
        return jsonify({'error': 'scene not found'}), 404
    return jsonify(scene)


@api.route('/scenes/history', methods=['GET'])
def scene_history():
    limit = int(request.args.get('limit', 50))
    return jsonify(crud.fetch_scene_history(limit=limit))


@api.route('/scenes/activate', methods=['POST'])
def scenes_activate():
    payload = request.get_json(silent=True) or {}
    scene_key = (payload.get('scene_key') or payload.get('scene_name') or '').strip()
    if not scene_key:
        return jsonify({'error': 'scene_key is required'}), 400

    scene = crud.fetch_scene_detail(scene_key)
    if not scene:
        return jsonify({'error': f"Khong tim thay scene '{scene_key}'"}), 404
    if not scene.get('is_active', True):
        return jsonify({'error': 'scene is inactive'}), 400

    user = None
    try:
        user = _get_auth_user(optional=True)
    except PermissionError as exc:
        return jsonify({'error': str(exc)}), 401

    user_id = int(user['id']) if user and user.get('id') is not None else None
    scene_id = crud.resolve_scene_id(scene['scene_key'])

    action_results = []
    action_errors = []

    for action in scene.get('actions', []):
        device_key = action['device_key']
        command = action.get('command')
        try:
            mqtt_result = publisher.control_device(device_key, command)
            device_state = crud.apply_device_command_state(device_key, command)
            crud.insert_device_log(
                device_name=device_key,
                action='scene_activated',
                status='success',
                triggered_by_user_id=user_id,
                triggered_by_scene_id=scene_id,
                action_source='scene',
                action_value=str(command),
            )
            action_results.append(
                {
                    'device_key': device_key,
                    'command': command,
                    'mqtt': mqtt_result,
                    'device_state': device_state,
                }
            )
        except ValueError as exc:
            crud.insert_device_log(
                device_name=device_key,
                action='scene_activated',
                status='failed',
                triggered_by_user_id=user_id,
                triggered_by_scene_id=scene_id,
                action_source='scene',
                action_value=str(command),
            )
            action_errors.append({'device_key': device_key, 'command': command, 'error': str(exc)})
        except Exception as exc:
            crud.insert_device_log(
                device_name=device_key,
                action='scene_activated',
                status='failed',
                triggered_by_user_id=user_id,
                triggered_by_scene_id=scene_id,
                action_source='scene',
                action_value=str(command),
            )
            action_errors.append(
                {
                    'device_key': device_key,
                    'command': command,
                    'error': f'Loi dieu khien scene: {exc}',
                }
            )

    crud.insert_activity_log(
        activity_type='scene_activated',
        entity_type='scenes',
        entity_id=scene_id,
        user_id=user_id,
        detail={
            'scene_key': scene['scene_key'],
            'scene_name': scene['scene_name'],
            'action_count': len(scene.get('actions', [])),
            'success_count': len(action_results),
            'error_count': len(action_errors),
        },
    )

    if action_errors:
        return (
            jsonify(
                {
                    'status': 'partial',
                    'scene': scene,
                    'results': action_results,
                    'errors': action_errors,
                }
            ),
            500,
        )

    return jsonify(
        {
            'status': 'ok',
            'scene': scene,
            'results': action_results,
        }
    )


@api.route('/logs', methods=['GET', 'POST'])
def logs():
    if request.method == 'GET':
        limit = int(request.args.get('limit', 100))
        rows = crud.fetch_device_logs(limit)
        data = [
            {'id': r[0], 'timestamp': r[1], 'device_name': r[2], 'action': r[3], 'status': r[4]}
            for r in rows
        ]
        return jsonify(data)

    payload = request.get_json(silent=True) or {}
    device_name = payload.get('device_name')
    action = payload.get('action')
    status = payload.get('status', 'OK')
    if not device_name or not action:
        return jsonify({'error': 'device_name and action required'}), 400
    crud.insert_device_log(device_name, action, status)
    return jsonify({'status': 'ok'})


def _sse_stream(fetch_fn, get_max_id_fn, transform):
    def gen():
        last_id = get_max_id_fn()
        while True:
            rows = fetch_fn(200)
            new_rows = [r for r in reversed(rows) if r[0] > last_id]
            for row in new_rows:
                payload = transform(row)
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                last_id = row[0]
            time.sleep(1)

    return gen


@api.route('/stream/sensor')
def stream_sensor():
    gen = _sse_stream(
        crud.fetch_latest_sensor_data,
        crud.get_max_sensor_id,
        lambda r: {
            'id': r[0],
            'timestamp': r[1],
            'temperature': r[2],
            'humidity': r[3],
            'gas_level': r[4],
        },
    )
    return Response(gen(), mimetype='text/event-stream')


@api.route('/stream/logs')
def stream_logs():
    gen = _sse_stream(
        crud.fetch_device_logs,
        crud.get_max_log_id,
        lambda r: {
            'id': r[0],
            'timestamp': r[1],
            'device_name': r[2],
            'action': r[3],
            'status': r[4],
        },
    )
    return Response(gen(), mimetype='text/event-stream')


@api.route('/', methods=['GET'])
def root():
    return jsonify({'message': 'Smart Home API is running', 'health': '/api/health'}), 200

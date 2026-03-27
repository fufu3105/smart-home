import os
from pathlib import Path

from flask import Flask, abort, send_from_directory
from flask_cors import CORS

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional in local setups
    def load_dotenv(*_args, **_kwargs):
        return False


BASE_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = BASE_DIR / 'backend'
FRONTEND_DIR = BASE_DIR / 'frontend'
ENV_FILE = BACKEND_DIR / '.env'

load_dotenv(ENV_FILE, override=True)


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'smart-home-dev-secret')
    app.config['JSON_AS_ASCII'] = False
    CORS(app)

    from api.routes import api
    from database import crud

    app.register_blueprint(api)

    crud.ensure_tables()
    crud.seed_sample_data()

    mqtt_sync_enabled = str(os.getenv('MQTT_SYNC_ENABLED', '1')).strip().lower() not in {'0', 'false', 'no'}
    if mqtt_sync_enabled:
        try:
            from mqtt.subscriber import start_background_subscriber

            start_background_subscriber()
        except Exception as exc:
            print(f'[MQTT] Khong khoi dong duoc dong bo nen: {exc}')

    @app.get('/')
    def serve_index():
        return send_from_directory(FRONTEND_DIR, 'index.html')

    @app.get('/<path:path>')
    def serve_frontend(path: str):
        target = FRONTEND_DIR / path
        if not target.is_file():
            abort(404)
        return send_from_directory(FRONTEND_DIR, path)

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=int(os.getenv('API_PORT', '5000')), debug=True)

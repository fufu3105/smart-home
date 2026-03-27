import json, traceback
from backend.main import create_app

def run():
    app = create_app()
    # propagate exceptions to see tracebacks in this script
    app.testing = True
    client = app.test_client()
    try:
        resp = client.post('/api/login', json={'username':'admin','password':'adminpass'})
        print('STATUS', resp.status_code)
        try:
            print(resp.get_data(as_text=True))
        except Exception:
            print('<no body>')
    except Exception:
        print('EXCEPTION during request:')
        traceback.print_exc()

if __name__ == '__main__':
    run()
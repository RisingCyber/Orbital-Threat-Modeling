"""
Local development launcher.

    python run.py

For anything beyond local development, set SPARTA_SECRET_KEY and
SPARTA_ENV=production and run under a real WSGI server (gunicorn/uwsgi)
behind TLS, per README.md "Running in production".
"""
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)

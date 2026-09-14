"""WSGI entry point for production servers, e.g.:
    gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app
Requires SPARTA_ENV=production and SPARTA_SECRET_KEY to be set in the
environment; see README.md.
"""
from app import create_app

app = create_app()

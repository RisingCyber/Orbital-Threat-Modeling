import os
import secrets

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from flask_talisman import Talisman

db = SQLAlchemy()
csrf = CSRFProtect()

# A strict Content-Security-Policy. No inline scripts/styles, no remote
# script sources - everything the UI needs ships from our own /static/.
CSP = {
    "default-src": "'self'",
    "script-src": "'self'",
    "style-src": "'self'",
    "img-src": "'self' data:",
    "font-src": "'self'",
    "connect-src": "'self'",
    "object-src": "'none'",
    "base-uri": "'self'",
    "frame-ancestors": "'none'",
}


def create_app(config_object=None):
    app = Flask(__name__, instance_relative_config=True)

    if config_object is None:
        env = os.environ.get("SPARTA_ENV", "development")
        config_object = "config.ProdConfig" if env == "production" else "config.DevConfig"
    app.config.from_object(config_object)

    os.makedirs(app.instance_path, exist_ok=True)

    if not app.config.get("SECRET_KEY"):
        if app.config.get("DEBUG"):
            # Dev-only convenience: an ephemeral key so `flask run` works
            # out of the box. Sessions won't survive a restart, which is
            # fine for local development and forces prod to set its own.
            app.config["SECRET_KEY"] = secrets.token_hex(32)
        else:
            raise RuntimeError(
                "SPARTA_SECRET_KEY environment variable is not set. "
                "Refusing to start with no secret key outside debug mode."
            )

    db.init_app(app)
    csrf.init_app(app)

    # HTTPS enforcement and security headers. force_https is disabled in
    # debug so local http://127.0.0.1 testing keeps working; a real
    # deployment should sit behind TLS and can leave this at its default.
    Talisman(
        app,
        content_security_policy=CSP,
        force_https=not app.config.get("DEBUG", False),
        strict_transport_security=True,
        session_cookie_secure=app.config.get("SESSION_COOKIE_SECURE", True),
        x_content_type_options=True,
        frame_options="DENY",
    )

    from app.routes.main import main_bp
    from app.routes.systems import systems_bp
    from app.routes.matrix import matrix_bp
    from app.routes.compliance import compliance_bp
    from app.routes.reports import reports_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(systems_bp)
    app.register_blueprint(matrix_bp)
    app.register_blueprint(compliance_bp)
    app.register_blueprint(reports_bp)

    from app import models  # noqa: F401  (ensure models are registered before create_all)

    with app.app_context():
        db.create_all()
        from app.data_loader import sync_reference_data
        sync_reference_data()

    @app.errorhandler(404)
    def not_found(_e):
        return {"error": "Not found"}, 404

    @app.errorhandler(413)
    def too_large(_e):
        return {"error": "Request too large"}, 413

    @app.errorhandler(500)
    def server_error(_e):
        # Deliberately generic - never reflect exception internals to the client.
        return {"error": "Internal server error"}, 500

    return app

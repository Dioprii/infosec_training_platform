"""Академия безопасности «Северный Контур»: Flask + SQLite."""
import os

from flask import Flask, jsonify, send_from_directory
from werkzeug.exceptions import HTTPException

from .config import Config
from .content import Course
from .db import close_db, get_db, init_db
from .security import ApiError, add_headers, origin_guard


def create_app(overrides=None):
    app = Flask(__name__, static_folder=None)
    app.config.from_object(Config)
    app.config.update(overrides or {})
    if app.config["TRUST_PROXY"]:
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    init_db(app.config["DB_PATH"])
    app.extensions["course"] = Course(app.config["CONTENT_PATH"])
    app.teardown_appcontext(close_db)
    app.before_request(origin_guard)
    app.after_request(add_headers)

    from . import routes_admin, routes_auth, routes_learn
    app.register_blueprint(routes_auth.bp, url_prefix="/api")
    app.register_blueprint(routes_learn.bp, url_prefix="/api")
    app.register_blueprint(routes_admin.bp, url_prefix="/api/admin")

    @app.errorhandler(ApiError)
    def api_error(e):
        try:
            get_db().rollback()
        except Exception:
            pass
        return jsonify(error=e.msg, field=e.field), e.code

    @app.errorhandler(HTTPException)
    def http_error(e):
        from flask import request
        if request.path.startswith("/api/"):
            return jsonify(error=e.description or e.name), e.code
        return e

    @app.get("/certificate/<code>")
    def certificate(code):
        return routes_learn.certificate_page(code)

    @app.get("/healthz")
    def healthz():
        get_db().execute("SELECT 1")
        return jsonify(ok=True)

    front = app.config["FRONTEND_DIR"]

    @app.get("/")
    def index():
        return send_from_directory(front, "index.html", max_age=0)

    @app.get("/<path:path>")
    def assets(path):
        if path.startswith("api/"):
            return jsonify(error="Не найдено"), 404
        resp = send_from_directory(front, path)
        if path.startswith("assets/"):
            resp.headers["Cache-Control"] = "public, max-age=604800"
        else:
            resp.headers["Cache-Control"] = "no-cache"
        return resp

    return app

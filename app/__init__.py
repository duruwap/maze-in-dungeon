"""미로 인 던전 Flask 앱."""
import os

from flask import Flask, jsonify, render_template, request

from .config import Config

APP_VERSION = "1.0.0"


def create_app(test_config=None):
    app = Flask(__name__, static_folder="../static", static_url_path="/static",
                template_folder="templates")
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    os.makedirs(app.config["OG_CACHE_DIR"], exist_ok=True)
    from .logutil import configure
    configure(None if app.config.get("TESTING") else app.config.get("LOG_DIR"))

    from . import db
    db.init_app(app)

    from .api import bp as api_bp
    app.register_blueprint(api_bp)
    try:
        from .share import bp as share_bp
        app.register_blueprint(share_bp)
    except ImportError:   # 5단계 이전
        pass

    from .i18n import pick_lang, texts

    @app.get("/")
    def index():
        lang = pick_lang(request)
        boot = {"kakaoKey": app.config["KAKAO_JS_KEY"], "baseUrl": app.config["BASE_URL"],
                "version": APP_VERSION}
        return render_template("index.html", lang=lang, cfg=app.config, texts=texts(lang),
                               boot=boot, version=APP_VERSION)

    @app.errorhandler(404)
    def not_found(_e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "not_found"}), 404
        return "Not Found", 404

    @app.errorhandler(Exception)
    def server_error(e):
        from werkzeug.exceptions import HTTPException
        if isinstance(e, HTTPException):
            return e
        app.logger.exception("unhandled error")
        return jsonify({"error": "server_error"}), 500

    return app

"""미로 인 던전 Flask 앱."""
import logging
import os

from flask import Flask, jsonify, render_template, request

from .config import Config


def create_app(test_config=None):
    app = Flask(__name__, static_folder="../static", static_url_path="/static",
                template_folder="templates")
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    os.makedirs(app.config["OG_CACHE_DIR"], exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    from . import db
    db.init_app(app)

    from .api import bp as api_bp
    app.register_blueprint(api_bp)
    try:
        from .share import bp as share_bp
        app.register_blueprint(share_bp)
    except ImportError:   # 5단계 이전
        pass

    @app.get("/")
    def index():
        lang = request.args.get("lang")
        if lang not in ("ko", "en", "zh", "ja"):
            lang = (request.accept_languages.best_match(["ko", "en", "zh", "ja"]) or "en")
        return render_template("index.html", lang=lang, cfg=app.config)

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

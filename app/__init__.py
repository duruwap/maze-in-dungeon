"""미로 인 던전 Flask 앱."""
import os

from flask import Flask, jsonify, render_template, request

from .config import Config

APP_VERSION = "1.0.0"
STATIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static"))


def asset_version():
    """정적 파일 내용이 바뀌면 달라지는 버전 문자열 (배포 즉시 브라우저 캐시 무효화)."""
    import hashlib
    h = hashlib.sha1()
    for sub in ("js", "css", "i18n", "assets"):
        root = os.path.join(STATIC_DIR, sub)
        for dirpath, _dirs, files in sorted(os.walk(root)):
            for fn in sorted(files):
                p = os.path.join(dirpath, fn)
                h.update(fn.encode())
                with open(p, "rb") as f:
                    h.update(f.read())
    return h.hexdigest()[:10]


def js_modules():
    return sorted(f for f in os.listdir(os.path.join(STATIC_DIR, "js")) if f.endswith(".js"))


def public_base():
    """카카오 등 외부에서 접근할 공개 주소. 설정값이 비었거나 로컬 주소면 현재 요청 주소를 쓴다."""
    from flask import current_app
    b = current_app.config.get("BASE_URL") or ""
    if not b or "://localhost" in b or "://127.0.0.1" in b:
        b = request.host_url
    return b.rstrip("/")


def create_app(test_config=None):
    app = Flask(__name__, static_folder="../static", static_url_path="/static",
                template_folder="templates")
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    os.makedirs(app.config["OG_CACHE_DIR"], exist_ok=True)
    from .logutil import configure
    configure(None if app.config.get("TESTING") else app.config.get("LOG_DIR"))

    # nginx 뒤에서 https/도메인을 올바르게 인식 (X-Forwarded-Proto, X-Forwarded-Host)
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

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

    version = asset_version()
    if not app.config.get("TESTING"):
        from .share.card import warm_up
        warm_up(app.config["OG_CACHE_DIR"])   # 첫 카드 생성 지연(수 초) 제거 — 카카오 이미지 수집 타임아웃 방지
    modules = js_modules()

    @app.after_request
    def no_cache_html(resp):
        # HTML/API 는 캐시하지 않는다 (정적 파일은 ?v= 버전으로 캐시)
        if resp.mimetype in ("text/html", "application/json") and not request.path.startswith("/static/"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.get("/")
    def index():
        lang = pick_lang(request)
        base = public_base()
        boot = {"kakaoKey": app.config["KAKAO_JS_KEY"], "baseUrl": base, "version": version}
        return render_template("index.html", lang=lang, cfg=app.config, texts=texts(lang),
                               boot=boot, version=version, modules=modules, base=base)

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

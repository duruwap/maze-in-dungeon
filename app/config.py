"""환경변수 기반 설정."""
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    BASE_URL = os.environ.get("BASE_URL", "http://localhost:15003").rstrip("/")
    KAKAO_JS_KEY = os.environ.get("KAKAO_JS_KEY", "")
    # Kakao JS SDK: 버전/무결성 해시는 공식 문서에서 확인 후 환경변수로 교체 가능
    KAKAO_SDK_URL = os.environ.get(
        "KAKAO_SDK_URL", "https://t1.kakaocdn.net/kakao_js_sdk/2.7.4/kakao.min.js")
    KAKAO_SDK_INTEGRITY = os.environ.get(
        "KAKAO_SDK_INTEGRITY",
        "sha384-DKYJZ8NLiK8MN4/C5P2dtSmLQ4KwPaoqAfyA/DfmEc1VDxu4yyC7wy6K1Hs90nka")
    DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "instance", "maze.db"))
    OG_CACHE_DIR = os.environ.get("OG_CACHE_DIR", os.path.join(BASE_DIR, "instance", "og_cache"))
    FONT_PATH = os.environ.get("FONT_PATH", "")
    PORT = int(os.environ.get("PORT", "15003"))
    SEND_FILE_MAX_AGE_DEFAULT = int(os.environ.get("STATIC_MAX_AGE", "0"))
    RATE_LIMIT_PER_MIN = 10

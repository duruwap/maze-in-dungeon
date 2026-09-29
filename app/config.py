"""환경변수 기반 설정."""
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP_NAME = "maze-in-dungeon"

# 서버 표준 경로: 앱 /scsrun/app/<레포>, 데이터 /scsdat/app/<레포>, 로그 /scslog/app/<레포>
# (해당 루트가 없는 로컬 개발 환경에서는 instance/ 와 stderr 로그를 쓴다)
_SCSDAT = f"/scsdat/app/{APP_NAME}"
_SCSLOG = f"/scslog/app/{APP_NAME}"
DATA_DIR = os.environ.get("DATA_DIR") or (_SCSDAT if os.path.isdir("/scsdat/app") else os.path.join(BASE_DIR, "instance"))
LOG_DIR = os.environ.get("LOG_DIR") or (_SCSLOG if os.path.isdir("/scslog/app") else "")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    # 공유 링크·OG 이미지의 공개 주소. 비어 있으면 요청 주소(nginx 의 Host/X-Forwarded-Proto)로 자동 판별
    BASE_URL = os.environ.get("BASE_URL", "").rstrip("/")
    KAKAO_JS_KEY = os.environ.get("KAKAO_JS_KEY", "")
    # Kakao JS SDK: 버전/무결성 해시는 공식 문서에서 확인 후 환경변수로 교체 가능
    KAKAO_SDK_URL = os.environ.get(
        "KAKAO_SDK_URL", "https://t1.kakaocdn.net/kakao_js_sdk/2.7.4/kakao.min.js")
    KAKAO_SDK_INTEGRITY = os.environ.get(
        "KAKAO_SDK_INTEGRITY",
        "sha384-DKYJZ8NLiK8MN4/C5P2dtSmLQ4KwPaoqAfyA/DfmEc1VDxu4yyC7wy6K1Hs90nka")
    DB_PATH = os.environ.get("DB_PATH", os.path.join(DATA_DIR, "maze.db"))
    OG_CACHE_DIR = os.environ.get("OG_CACHE_DIR", os.path.join(DATA_DIR, "og_cache"))
    LOG_DIR = LOG_DIR
    FONT_PATH = os.environ.get("FONT_PATH", "")
    PORT = int(os.environ.get("PORT", "15003"))
    SEND_FILE_MAX_AGE_DEFAULT = int(os.environ.get("STATIC_MAX_AGE", "0"))
    RATE_LIMIT_PER_MIN = 10

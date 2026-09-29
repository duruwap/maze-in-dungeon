# 미로 인 던전 (Maze in Dungeon)

시작할 때마다 새로 생성되는 어두운 던전 미로에서 발밑만 보이는 채로 출발해, 횃불을 켜고 텔레포트를 열며 열쇠를 모두 모은 뒤
중앙 탈출 방의 문을 열고 나가는 시간을 겨루는 1인용 웹 게임입니다.

- 시작할 때마다 새 맵을 생성하는 **오늘의 던전**(보통 난이도, 날짜별 랭킹 — 한국 시간 자정 초기화)
- 난이도별 **자유 탐험**(쉬움/보통/어려움, 주간 랭킹 — 월요일 KST 초기화)
- 로그인·닉네임 없이 `탐험가 #번호`로 순위·상위 %를 보여주고 카카오톡/링크로 공유
- 한국어 · English · 简体中文 · 日本語

글꼴: 화면·공유 페이지·결과 카드 모두 [Pretendard](https://github.com/orioncactus/pretendard)(OFL, `static/fonts/`에 자체 호스팅,
동적 서브셋이라 필요한 글자 조각만 내려받음). 일본어 한자는 Pretendard JP, Pretendard에 없는 중국어 간체 글자는 시스템 CJK 글꼴로 대체.

기술: Python 3.11 + Flask 3 + SQLite(WAL) / Vanilla JS(ES Modules) + Canvas 2D / Web Audio 합성 사운드 /
Pillow로 생성한 픽셀 아트. 빌드 도구 없음.

---

## 1. 로컬 실행

```bash
git clone <repo> maze-in-dungeon && cd maze-in-dungeon
./startup.sh dev                    # venv 생성 + 의존성 + Flask 개발 서버 (http://localhost:15003)
```

- `/scsdat/app`가 없는 로컬 환경에서는 DB가 `instance/maze.db`에, 로그는 터미널(stderr)에 남습니다.
- 스프라이트는 `static/assets/`에 커밋되어 있습니다. 다시 만들려면 `python tools/make_sprites.py`
  (검토용 전체 시트는 `static/assets/_preview.png`).

### 서버 경로 규칙

| 구분 | 경로 |
|---|---|
| 앱 | `/scsrun/app/maze-in-dungeon` |
| PID | `/scsrun/pid/maze-in-dungeon.pid` |
| 데이터 | `/scsdat/app/maze-in-dungeon/` — `maze.db`(SQLite, WAL), `og_cache/`(결과 카드), `backups/` |
| 로그 | `/scslog/app/maze-in-dungeon/app-YYYY-MM-DD.log` (일별, 앱 + gunicorn 접근/에러 로그), `console.log`(stderr 캡처) |

`/scsdat/app`, `/scslog/app` 디렉토리가 있으면 앱이 자동으로 위 경로를 씁니다. `startup.sh`도 같은 값을 명시적으로 넘깁니다.

### 설정

- 포트·워커 수·경로·로그 보관 일수: `scsrun.conf` (git에 포함, 기본 포트 15003)
- 비밀값: 프로젝트의 `.env` (git 제외, `.env.example` 참고)

| 이름 | 기본값 | 설명 |
|---|---|---|
| `SECRET_KEY` | `dev-secret-change-me` | 운영에서는 반드시 긴 무작위 문자열 |
| `BASE_URL` | `http://localhost:15003` | 공유 링크·OG 이미지 절대 주소 (운영: `https://maze.duruwap.com`) |
| `KAKAO_JS_KEY` | (없음) | 카카오 JavaScript 키. 없으면 카카오 버튼만 숨고 나머지는 정상 동작 |
| `DATA_DIR` / `DB_PATH` / `OG_CACHE_DIR` | `/scsdat/app/maze-in-dungeon` 하위 | 데이터 경로 |
| `LOG_DIR` | `/scslog/app/maze-in-dungeon` | 일별 로그 디렉토리 |
| `PORT` | `15003` | 서비스 포트 |
| `FONT_PATH` | (없음) | 결과 카드 중국어 간체용 대체 폰트. 없으면 시스템 Noto Sans CJK → WenQuanYi 순으로 찾음 (한국어·영어·일본어는 Pretendard) |
| `KAKAO_SDK_URL`, `KAKAO_SDK_INTEGRITY` | 2.7.4 | Kakao SDK 버전/SRI 해시 교체용 |

## 2. 테스트

```bash
pip install -r requirements-dev.txt  # pytest, playwright (서버 운영에는 불필요)
python -m pytest                    # 서버 테스트 (맵 생성 3,000개 포함, 약 1분)
python -m pytest tests/e2e_smoke.py # Playwright 스모크 (Chromium 필요: playwright install chromium)
```

| 파일 | 내용 |
|---|---|
| `tests/test_generator.py` | 결정성, 3난이도 × 1,000 시드 도달성·열쇠 수·구역·텔레포트 간격·탈출 방/광장 위치, hard 생성 200ms 이하 |
| `tests/test_runs.py` | 정상 제출, 토큰 재사용/타인 토큰 거부, 너무 빠른 기록, 서버 경과 시간 초과, 분당 제한, 입력 검증, 공유/OG 4개 언어 |
| `tests/test_rank.py` | 플레이어당 최고 기록만 반영, 동점 처리, 상위 % 계산, 10명 미만 분기, 상위 100 + 내 순위 |
| `tests/test_logutil.py` | 날짜가 바뀌면 새 로그 파일(`app-YYYY-MM-DD.log`)에 기록 |
| `tests/test_i18n.py` | 4개 언어 키 집합·변수 일치, 핵심 용어, 코드에서 쓰는 키가 모두 존재 |
| `tests/e2e_smoke.py` | 타이틀 → 쉬움 시작 → 캔버스 렌더 → 콘솔 에러 0 → 4개 언어 전환 (PC·390×844) |

개발용 자동 플레이(실제 브라우저에서 봇이 3난이도를 클리어하고 스크린샷 저장):

```bash
python wsgi.py &
python tools/autoplay.py --out docs/screenshots            # PC
python tools/autoplay.py --out docs/screenshots --mobile   # 390×844
```

## 3. 배포 (Ubuntu + startup.sh(gunicorn) + nginx)

```bash
# 1) 디렉토리 (최초 1회)
sudo mkdir -p /scsrun/app /scsrun/pid /scsdat/app/maze-in-dungeon /scslog/app/maze-in-dungeon
sudo chown -R ubuntu: /scsrun /scsdat/app/maze-in-dungeon /scslog/app/maze-in-dungeon
sudo apt install -y python3-venv git curl fonts-noto-cjk   # fonts-noto-cjk: 결과 카드 중국어 간체 대체 글꼴 (권장)

# 2) 코드와 비밀값
cd /scsrun/app && git clone <repo> maze-in-dungeon && cd maze-in-dungeon
cp .env.example .env && nano .env         # SECRET_KEY, BASE_URL, KAKAO_JS_KEY

# 3) 기동 (기존 프로세스 종료 → git pull → venv/의존성 → gunicorn 데몬 → 응답 확인)
./startup.sh
./startup.sh status                        # pid, 응답 코드, 오늘 로그 경로
./startup.sh logs                          # 오늘 로그 tail -F

# 4) nginx + HTTPS
sudo cp deploy/nginx.conf /etc/nginx/sites-available/maze.duruwap.com
sudo ln -s /etc/nginx/sites-available/maze.duruwap.com /etc/nginx/sites-enabled/
sudo apt install -y certbot python3-certbot-nginx
sudo certbot certonly --nginx -d maze.duruwap.com
sudo nginx -t && sudo systemctl reload nginx
```

| 명령 | 동작 |
|---|---|
| `./startup.sh` | 종료 → `git pull --ff-only` → 의존성 → 기동 (포트 15003) |
| `./startup.sh --no-pull` | git pull 없이 재기동 |
| `./startup.sh stop` / `status` / `logs` | 종료 / 상태 / 오늘 로그 보기 |
| `./startup.sh dev` | Flask 개발 서버(포그라운드, 자동 리로드) |

- 실제 동작은 공통 런처 `scripts/scs-run.sh`가 담당합니다 (`startup.sh`가 있는 디렉토리를 프로젝트로 사용).
- 기동 시 포트가 이미 사용 중이면 중단하고, 기동 후 `HEALTH_TIMEOUT`초 안에 응답이 없으면 실패로 끝납니다.
- 로그는 `app-YYYY-MM-DD.log`로 날짜마다 새 파일에 쌓이고, `LOG_KEEP_DAYS`(기본 30일)보다 오래된 파일은 기동 시 정리됩니다.
  서버 예외는 스택트레이스로 남고, 사용자에게는 짧은 안내만 보냅니다.
- 재부팅 자동 기동(선택): `sudo cp deploy/maze-in-dungeon.service /etc/systemd/system/ && sudo systemctl enable --now maze-in-dungeon`
  (내부적으로 `startup.sh --no-pull` / `startup.sh stop` 호출). 또는 crontab `@reboot /scsrun/app/maze-in-dungeon/startup.sh --no-pull`.
- DNS: `maze.duruwap.com` A 레코드를 서버 IP로.

### DB 백업

```bash
scripts/backup_db.sh      # /scsdat/app/maze-in-dungeon/backups/maze-YYYYmmdd-HHMMSS.db.gz (14일 보관)
# cron (매일 04:17)
17 4 * * * /scsrun/app/maze-in-dungeon/scripts/backup_db.sh >> /scslog/app/maze-in-dungeon/backup.log 2>&1
```

SQLite 온라인 백업 API를 쓰므로 서비스 중에도 안전합니다. 복구: `./startup.sh stop` 후 `gunzip`한 파일을
`/scsdat/app/maze-in-dungeon/maze.db`로 복사하고 `./startup.sh --no-pull`.

## 4. 카카오톡 공유 설정

1. [Kakao Developers](https://developers.kakao.com) → 내 애플리케이션 → 애플리케이션 추가.
2. **앱 키 → JavaScript 키**를 복사해 `.env`의 `KAKAO_JS_KEY`에 넣고 서비스를 재시작.
3. **플랫폼 → Web → 사이트 도메인**에 `https://maze.duruwap.com` 등록 (로컬 테스트 시 `http://localhost:15003`도).
4. 공유 메시지의 이미지/링크 도메인도 같은 도메인이어야 합니다 (`BASE_URL`과 일치).
5. SDK는 `https://t1.kakaocdn.net/kakao_js_sdk/2.7.4/kakao.min.js`를 `integrity` 속성과 함께 불러옵니다.
   새 버전을 쓰려면 [공식 문서](https://developers.kakao.com/docs/latest/ko/javascript/getting-started)의 URL·해시로
   `KAKAO_SDK_URL`/`KAKAO_SDK_INTEGRITY`를 바꾸세요. 해시가 틀리면 브라우저가 SDK를 막고 카카오 버튼만 숨겨집니다.

카카오톡이 없는 환경에서는 Web Share API(지원 브라우저)와 링크 복사가 동작합니다.

## 5. 구조

```
app/            Flask 앱 (API, 맵 생성, 공유/OG 카드)
  maze/         generator.py (Rooms and Mazes + Growing Tree + 브레이딩), placement.py, validate.py
static/js/      main, config(모든 수치), game, render, lighting, fov, input, minimap, hud, audio, i18n, api, share, storage, sprites, particles
static/i18n/    ko/en/zh/ja.json
static/assets/  생성된 스프라이트 PNG + atlas.json + _preview.png
tools/          make_sprites.py, autoplay.py/js
startup.sh      기동 스크립트 (scripts/scs-run.sh 공통 런처 호출), scsrun.conf 설정
deploy/         gunicorn(일별 로그 포함), systemd(선택), nginx 설정
```

게임 수치는 `static/js/config.js` 한 곳에서 조정합니다. 이동 속도·상호작용 거리·문 열기 시간을 바꾸면
서버의 `app/maze/validate.py`(부정 기록 하한)도 함께 맞춰 주세요. 명세와 다르게 정한 사항은 `DECISIONS.md`에 있습니다.

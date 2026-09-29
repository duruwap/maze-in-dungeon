"""Playwright 스모크 테스트: 타이틀 → 게임 시작(1라운드) → 캔버스 렌더 → 콘솔 에러 0 → 언어 전환.

실행: python -m pytest tests/e2e_smoke.py  (Chromium 필요)
"""
import os
import socket
import threading

import pytest

pw = pytest.importorskip("playwright.sync_api")

from werkzeug.serving import make_server  # noqa: E402

from app import create_app  # noqa: E402

CHROME = os.environ.get("CHROME", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome")


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("e2e")
    app = create_app({"TESTING": True, "DB_PATH": str(tmp / "e2e.db"), "OG_CACHE_DIR": str(tmp / "og")})
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    srv = make_server("127.0.0.1", port, app, threaded=True)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    yield f"http://127.0.0.1:{port}"
    srv.shutdown()


@pytest.fixture(scope="module")
def browser():
    with pw.sync_playwright() as p:
        kw = {"executable_path": CHROME} if os.path.exists(CHROME) else {}
        b = p.chromium.launch(**kw)
        yield b
        b.close()


def canvas_has_pixels(page):
    return page.evaluate("""() => {
        const c = document.getElementById('game');
        const tmp = document.createElement('canvas');
        tmp.width = 64; tmp.height = 64;
        const x = tmp.getContext('2d');
        x.drawImage(c, c.width / 2 - 200, c.height / 2 - 200, 400, 400, 0, 0, 64, 64);
        const d = x.getImageData(0, 0, 64, 64).data;
        let bright = 0;
        for (let i = 0; i < d.length; i += 4) if (d[i] + d[i + 1] + d[i + 2] > 120) bright++;
        return bright;
    }""")


@pytest.mark.parametrize("viewport", [{"width": 1280, "height": 800}, {"width": 390, "height": 844}])
def test_smoke(server, browser, viewport):
    ctx = browser.new_context(viewport=viewport, locale="ko-KR")
    page = ctx.new_page()
    errors = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(server + "/")
    page.wait_for_selector("#screen-title:not([hidden])")
    assert page.inner_text("#screen-title h1") == "미로 인 던전"
    page.wait_for_function("document.getElementById('explorer-name').textContent.length > 0")

    assert page.locator("#screen-title button.btn").count() == 1   # 메인 화면에는 게임 시작 버튼만
    page.click("#btn-start")
    page.wait_for_selector("#hud:not([hidden])")
    page.keyboard.down("ArrowUp")
    page.wait_for_timeout(400)
    page.keyboard.up("ArrowUp")
    page.wait_for_timeout(300)
    assert canvas_has_pixels(page) > 50
    assert page.inner_text("#timer") != "0:00.00"
    assert page.locator("#keyslots canvas").count() == 2   # 1라운드(쉬움)
    assert "1/3" in page.inner_text("#round-label")

    # 일시정지 → 언어 전환 → 누락 문구 없음
    page.keyboard.press("Escape")
    page.wait_for_selector("#modal-pause:not([hidden])")
    for lang, title in (("en", "Maze in Dungeon"), ("zh", "地牢迷宫"), ("ja", "ダンジョン迷宮"), ("ko", "미로 인 던전")):
        page.click("#btn-lang")
        page.click(f".btn.lang[data-lang={lang}]")
        page.wait_for_function(f"document.title === {title!r}")
        texts = page.evaluate("[...document.querySelectorAll('[data-i18n]')].map(e => [e.dataset.i18n, e.textContent])")
        leaked = [k for k, v in texts if v == k or not v.strip()]
        assert not leaked, (lang, leaked)
    page.click("#btn-totitle")
    page.wait_for_selector("#screen-title:not([hidden])")
    assert not errors, errors
    ctx.close()

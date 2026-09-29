#!/usr/bin/env python3
"""개발용: 실제 브라우저에서 봇이 3라운드(쉬움→보통→어려움)를 클리어하고 스크린샷을 남긴다.

사용: 서버 실행 후 python tools/autoplay.py [--base http://localhost:15003] [--out docs/screenshots]
"""
import argparse
import asyncio
import os

from playwright.async_api import async_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
CHROME = os.environ.get("CHROME", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome")


async def run(base, out, runs=1, mobile=False):
    os.makedirs(out, exist_ok=True)
    bot = open(os.path.join(HERE, "autoplay.js")).read()
    async with async_playwright() as p:
        kw = {"executable_path": CHROME} if os.path.exists(CHROME) else {}
        b = await p.chromium.launch(**kw)
        results = {}
        for run_i in range(runs):
            ctx = await b.new_context(**({"viewport": {"width": 390, "height": 844}, "device_scale_factor": 2,
                                          "is_mobile": True, "has_touch": True} if mobile else
                                         {"viewport": {"width": 1280, "height": 800}}))
            pg = await ctx.new_page()
            errors = []
            pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            pg.on("pageerror", lambda e: errors.append(str(e)))
            await pg.goto(f"{base}/?lang=ko&debug=1")
            await pg.wait_for_timeout(800)
            await pg.add_script_tag(content=bot)
            sfx = "_mobile" if mobile else ""
            await pg.click("#btn-start")
            rounds = []
            for rnd in (1, 2, 3):
                await pg.wait_for_function(f"window.__mid && __mid.S.game && __mid.S.session.round === {rnd} && !__mid.S.game.finished")
                await pg.wait_for_timeout(400)
                await pg.evaluate("window.__bot = window.__autoplay({torches: true, teleports: true})")
                await pg.wait_for_timeout(1500)
                await pg.screenshot(path=os.path.join(out, f"game_round{rnd}_start{sfx}.png"))
                shot_mid = False
                for _ in range(4000):
                    await pg.wait_for_timeout(250)
                    st = await pg.evaluate("({done: window.__bot.done, t: __mid.S.game.elapsed, lit: __mid.S.game.litTorchCount()})")
                    if not shot_mid and st["lit"] >= 5:
                        await pg.screenshot(path=os.path.join(out, f"game_round{rnd}_torches{sfx}.png"))
                        shot_mid = True
                    if st["done"]:
                        break
                rounds.append(round(st["t"] / 1000, 1))
                if rnd < 3:
                    await pg.wait_for_selector("#round-clear:not([hidden])", timeout=10000)
                    await pg.wait_for_timeout(300)
                    await pg.screenshot(path=os.path.join(out, f"round{rnd}_clear{sfx}.png"))
            await pg.wait_for_selector("#screen-result:not([hidden])", timeout=15000)
            await pg.wait_for_timeout(1500)
            await pg.screenshot(path=os.path.join(out, f"result{sfx}.png"))
            rank = await pg.inner_text("#result-rank")
            total = await pg.inner_text("#result-time")
            results[run_i] = (rounds, total, rank, errors)
            print("run", results[run_i], flush=True)
            await ctx.close()
        await b.close()
        return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:15003")
    ap.add_argument("--out", default="docs/screenshots")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--mobile", action="store_true")
    a = ap.parse_args()
    asyncio.run(run(a.base, a.out, a.runs, a.mobile))

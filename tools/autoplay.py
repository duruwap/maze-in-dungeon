#!/usr/bin/env python3
"""개발용: 실제 브라우저에서 봇으로 각 난이도를 클리어하고 스크린샷을 남긴다.

사용: 서버 실행 후 python tools/autoplay.py [--base http://localhost:15003] [--out docs/screenshots]
"""
import argparse
import asyncio
import os

from playwright.async_api import async_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
CHROME = os.environ.get("CHROME", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome")


async def run(base, out, diffs, mobile=False):
    os.makedirs(out, exist_ok=True)
    bot = open(os.path.join(HERE, "autoplay.js")).read()
    async with async_playwright() as p:
        kw = {"executable_path": CHROME} if os.path.exists(CHROME) else {}
        b = await p.chromium.launch(**kw)
        results = {}
        for diff in diffs:
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
            await pg.click(f"[data-diff={diff}]")
            await pg.wait_for_function("window.__mid && window.__mid.S.game")
            await pg.wait_for_timeout(500)
            await pg.evaluate("window.__bot = window.__autoplay({torches: true, teleports: true})")
            shot_mid = False
            for i in range(2400):
                await pg.wait_for_timeout(250)
                st = await pg.evaluate("({done: window.__bot.done, t: __mid.S.game ? __mid.S.game.elapsed : 0,"
                                       " lit: __mid.S.game ? __mid.S.game.litTorchCount() : 0})")
                if not shot_mid and st["lit"] >= 6:
                    await pg.screenshot(path=os.path.join(out, f"game_{diff}_torches{'_mobile' if mobile else ''}.png"))
                    shot_mid = True
                if st["done"]:
                    break
            await pg.wait_for_selector("#screen-result:not([hidden])", timeout=10000)
            await pg.wait_for_timeout(1500)
            await pg.screenshot(path=os.path.join(out, f"result_{diff}{'_mobile' if mobile else ''}.png"))
            rank = await pg.inner_text("#result-rank")
            results[diff] = (round(st["t"] / 1000, 1), rank, errors)
            print(diff, results[diff], flush=True)
            await ctx.close()
        await b.close()
        return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:15003")
    ap.add_argument("--out", default="docs/screenshots")
    ap.add_argument("--diffs", default="easy,normal,hard")
    ap.add_argument("--mobile", action="store_true")
    a = ap.parse_args()
    asyncio.run(run(a.base, a.out, a.diffs.split(","), a.mobile))

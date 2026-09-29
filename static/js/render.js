// 월드 렌더링: 정적 맵 레이어(바닥·벽·장식) + 오브젝트 + 플레이어 + 조명 + 화면 효과.
import { CONFIG } from './config.js';
import { T_WALL, T_CORR, T_ROOM, T_EXIT, T_DOOR } from './game.js';
import { Lighting } from './lighting.js';

const TS = CONFIG.tile;

export function hash2(x, y, seed) {
  let h = (x * 374761393 + y * 668265263 + seed * 2246822519) | 0;
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  h ^= h >>> 16;
  return h >>> 0;
}

export class Renderer {
  constructor(canvas, sprites, particles) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d', { alpha: false });
    this.sprites = sprites;
    this.particles = particles;
    this.lighting = new Lighting();
    this.cam = { x: 0, y: 0, scale: 3, tp: 48, shakeT: 0, shakeAmp: 0, sx: 0, sy: 0 };
    this.settings = { shake: true, flicker: true };
    this.flashT = -1;
    this.vignette = null;
    this.game = null;
    this.resize();
  }

  resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 3);
    const w = Math.max(1, Math.round(window.innerWidth * dpr));
    const h = Math.max(1, Math.round(window.innerHeight * dpr));
    this.canvas.width = w;
    this.canvas.height = h;
    this.dpr = dpr;
    const short = Math.min(w, h);
    const scale = Math.max(CONFIG.minScale, Math.min(CONFIG.maxScale, Math.floor(short / (TS * CONFIG.targetTilesShort))));
    this.cam.scale = scale;
    this.cam.tp = TS * scale;
    this.lighting.resize(w, h);
    this.vignette = null;
    this.ctx.imageSmoothingEnabled = false;
  }

  setGame(game) {
    this.game = game;
    this.buildStatic();
    this.flashT = -1;
    const p = game.player;
    this.cam.x = p.x;
    this.cam.y = p.y;
  }

  // ---------- 정적 레이어 ----------
  buildStatic() {
    const g = this.game;
    const { W, H } = g;
    const seed = g.maze.floor_variant_seed | 0;
    const c = document.createElement('canvas');
    c.width = W * TS;
    c.height = H * TS;
    const ctx = c.getContext('2d');
    ctx.imageSmoothingEnabled = false;
    const S = this.sprites;
    const isWallish = (x, y) => {
      const t = g.tileAt(x, y);
      return t === T_WALL || t === T_DOOR;
    };
    for (let y = 0; y < H; y++) {
      for (let x = 0; x < W; x++) {
        const t = g.tiles[y * W + x];
        const px = x * TS;
        const py = y * TS;
        const hv = hash2(x, y, seed);
        if (t === T_CORR || t === T_ROOM || t === T_EXIT) {
          if (t === T_CORR) S.draw(ctx, `floor.corr.${[0, 0, 0, 1, 1, 2, 3][hv % 7]}`, px, py);
          else if (t === T_ROOM) S.draw(ctx, `floor.room.${hv % 5 === 0 ? 1 : 0}`, px, py);
          else S.draw(ctx, 'floor.exit.0', px, py);
          if (isWallish(x, y - 1)) S.draw(ctx, 'shade.n', px, py);
          if (isWallish(x - 1, y)) S.draw(ctx, 'shade.w', px, py);
          if (isWallish(x + 1, y)) S.draw(ctx, 'shade.e', px, py);
        }
      }
    }
    for (const d of g.maze.decor) {
      const v = hash2(d.x, d.y, seed + 7) % 2;
      S.draw(ctx, `decor.${d.kind}.${v}`, d.x * TS, d.y * TS);
    }
    for (let y = 0; y < H; y++) {
      for (let x = 0; x < W; x++) {
        if (g.tiles[y * W + x] !== T_WALL) continue;
        const px = x * TS;
        const py = y * TS;
        const hv = hash2(x, y, seed + 13);
        const below = g.tileAt(x, y + 1);
        if (y + 1 < H && below !== T_WALL && below !== T_DOOR) {
          const r = hv % 10;
          S.draw(ctx, `wall.face.${r < 6 ? 0 : r < 8 ? 1 : r < 9 ? 2 : 3}`, px, py);
        } else {
          let m = 0;
          if (y === 0 || isWallish(x, y - 1)) m |= 1;
          if (x === W - 1 || isWallish(x + 1, y)) m |= 2;
          if (y === H - 1 || isWallish(x, y + 1)) m |= 4;
          if (x === 0 || isWallish(x - 1, y)) m |= 8;
          S.draw(ctx, `wall.top.${m}`, px, py);
        }
      }
    }
    this.staticLayer = c;
  }

  // ---------- 효과 ----------
  shake(amp, ms) {
    if (!this.settings.shake) return;
    this.cam.shakeAmp = amp;
    this.cam.shakeT = ms / 1000;
    this.cam.shakeMax = ms / 1000;
  }

  flash() {
    this.flashT = 0;
  }

  _vignette(w, h) {
    if (this.vignette) return this.vignette;
    const c = document.createElement('canvas');
    c.width = w;
    c.height = h;
    const ctx = c.getContext('2d');
    const r = Math.hypot(w, h) / 2;
    const gr = ctx.createRadialGradient(w / 2, h / 2, r * 0.45, w / 2, h / 2, r);
    gr.addColorStop(0, 'rgba(5,6,12,0)');
    gr.addColorStop(1, 'rgba(5,6,12,0.75)');
    ctx.fillStyle = gr;
    ctx.fillRect(0, 0, w, h);
    this.vignette = c;
    return c;
  }

  // ---------- 프레임 ----------
  render(dt, time) {
    const g = this.game;
    if (!g) return;
    const ctx = this.ctx;
    const { width: W, height: H } = this.canvas;
    const cam = this.cam;
    const p = g.player;

    // 카메라: 플레이어를 부드럽게 따라간다
    const k = Math.min(1, dt * 12);
    cam.x += (p.x - cam.x) * k;
    cam.y += (p.y - cam.y) * k;
    if (Math.abs(p.x - cam.x) > 3 || Math.abs(p.y - cam.y) > 3) { cam.x = p.x; cam.y = p.y; }
    let sx = 0;
    let sy = 0;
    if (cam.shakeT > 0) {
      cam.shakeT -= dt;
      const a = cam.shakeAmp * (cam.shakeT / cam.shakeMax) * cam.tp;
      sx = (Math.random() * 2 - 1) * a;
      sy = (Math.random() * 2 - 1) * a;
    }
    const tp = cam.tp;
    const ox = Math.round(W / 2 - cam.x * tp + sx);
    const oy = Math.round(H / 2 - cam.y * tp + sy);
    this.ox = ox;
    this.oy = oy;

    const dark = this._darkColor(g);
    ctx.globalCompositeOperation = 'source-over';
    ctx.globalAlpha = 1;
    ctx.fillStyle = `rgb(${dark[0]},${dark[1]},${dark[2]})`;
    ctx.fillRect(0, 0, W, H);

    // 보이는 칸 범위
    const x0 = Math.max(0, Math.floor(-ox / tp) - 1);
    const y0 = Math.max(0, Math.floor(-oy / tp) - 1);
    const x1 = Math.min(g.W, Math.ceil((W - ox) / tp) + 1);
    const y1 = Math.min(g.H, Math.ceil((H - oy) / tp) + 1);
    this.view = { x0, y0, x1, y1 };

    ctx.imageSmoothingEnabled = false;
    if (x1 > x0 && y1 > y0) {
      ctx.drawImage(this.staticLayer, x0 * TS, y0 * TS, (x1 - x0) * TS, (y1 - y0) * TS,
        ox + x0 * tp, oy + y0 * tp, (x1 - x0) * tp, (y1 - y0) * tp);
    }

    this._drawObjects(ctx, g, time, ox, oy, tp);
    this._drawPlayer(ctx, g, time, ox, oy, tp);
    this.particles.draw(ctx, ox, oy, tp, 'under', g);

    // 조명
    let darkAlpha = 1;
    if (this.flashT >= 0) {
      this.flashT += dt * 1000;
      const f = this.flashT / CONFIG.clearFlashMs;
      darkAlpha = f < 0.25 ? 1 - f / 0.25 * 0.85 : Math.min(1, 0.15 + (f - 0.25) * 0.4);
    }
    this.lighting.render(ctx, g, { ox, oy, tp, W, H, time, dark, flicker: this.settings.flicker, darkAlpha });

    this._drawAboveDark(ctx, g, time, ox, oy, tp);
    this.particles.draw(ctx, ox, oy, tp, 'over', g);

    ctx.globalCompositeOperation = 'source-over';
    ctx.globalAlpha = 1;
    ctx.drawImage(this._vignette(W, H), 0, 0);
    if (this.flashT >= 0 && this.flashT < CONFIG.clearFlashMs) {
      const f = this.flashT / CONFIG.clearFlashMs;
      ctx.globalCompositeOperation = 'lighter';
      ctx.globalAlpha = Math.max(0, 0.35 * (1 - f));
      ctx.fillStyle = CONFIG.palette.torch;
      ctx.fillRect(0, 0, W, H);
      ctx.globalAlpha = 1;
      ctx.globalCompositeOperation = 'source-over';
    }
  }

  _darkColor(g) {
    const a = CONFIG.palette.dark;
    const b = CONFIG.palette.darkWarm;
    const f = g.torches.length ? Math.min(1, g.litTorchCount() / Math.max(8, g.torches.length * 0.6)) : 0;
    return [0, 1, 2].map((i) => Math.round(a[i] + (b[i] - a[i]) * f));
  }

  _inView(x, y) {
    const v = this.view;
    return x >= v.x0 - 1 && x <= v.x1 && y >= v.y0 - 1 && y <= v.y1;
  }

  _drawObjects(ctx, g, time, ox, oy, tp) {
    const S = this.sprites;
    const A = CONFIG.anim;
    const sc = this.cam.scale;
    // 탈출 방 출구
    const e = g.maze.exit;
    if (this._inView(e.x, e.y)) {
      S.draw(ctx, `exit.${Math.floor(time * 6) % 4}`, ox + e.x * tp, oy + e.y * tp, tp, tp);
    }
    // 텔레포트 석판
    g.teleports.forEach((t, i) => {
      if (!this._inView(t.x, t.y)) return;
      let name = 'tp.off';
      if (g.tpActive[i]) name = `tp.on.${Math.floor(time * A.tpFps) % 6}`;
      else if (g.action && g.action.type === 'tpActivate' && g.action.id === i) {
        name = `tp.on.${Math.floor(g.action.t / 80) % 6}`;
      }
      S.draw(ctx, name, ox + t.x * tp, oy + t.y * tp, tp, tp);
    });
    // 문
    const d = g.maze.door;
    if (this._inView(d.x, d.y)) {
      let name;
      if (g.doorOpen) name = 'door.open.3';
      else if (g.action && g.action.type === 'doorOpen') name = `door.open.${Math.min(3, Math.floor(g.doorAnim * 4))}`;
      else {
        let filled = g.insertedCount();
        if (g.action && g.action.type === 'door') filled += g.action.inserted;
        name = `door.${g.totalKeys}.${Math.min(filled, g.totalKeys)}`;
      }
      S.draw(ctx, name, ox + d.x * tp, oy + d.y * tp, tp, tp);
    }
    // 횃불 (벽에 붙어 있다)
    g.torches.forEach((t, i) => {
      if (!this._inView(t.x, t.y)) return;
      const lit = g.torchLit[i];
      const f = Math.floor(time * A.torchFps + i * 1.7) % 4;
      const side = t.wall === 'E' || t.wall === 'W' || t.wall === 'S';
      const name = side ? (lit ? `torch.side.on.${f}` : 'torch.side.off') : (lit ? `torch.on.${f}` : 'torch.off');
      let px = ox + (t.x + t.dx) * tp;
      let py = oy + (t.y + t.dy) * tp;
      if (t.wall === 'E') px -= tp * 0.5;
      if (t.wall === 'W') px += tp * 0.5;
      if (t.wall === 'S') py -= tp * 0.55;
      S.draw(ctx, name, px, py, tp, tp, t.wall === 'W');
      // 켜는 중
      if (g.action && g.action.type === 'torch' && g.action.id === i) {
        const k = g.action.t / g.action.dur;
        ctx.globalAlpha = k;
        S.draw(ctx, side ? `torch.side.on.${f}` : `torch.on.${f}`, px, py, tp, tp, t.wall === 'W');
        ctx.globalAlpha = 1;
      }
    });
    // 열쇠 (바닥에서 살짝 떠 있다)
    g.keys.forEach((k, i) => {
      if (g.keyState[i] !== 0 || !this._inView(k.x, k.y)) return;
      const bob = Math.round(Math.sin(time * 3 + i) * 1.5) * sc;
      S.draw(ctx, `key.${k.color}.${Math.floor(time * A.keyFps + i) % 4}`, ox + k.x * tp, oy + k.y * tp - sc * 2 + bob, tp, tp);
    });
  }

  _playerFrame(g, time) {
    const p = g.player;
    const A = CONFIG.anim;
    const a = g.action;
    if (a) {
      if (a.type === 'teleport') return `player.teleport.${Math.min(2, Math.floor(a.t / a.dur * 3))}`;
      if (a.type === 'arrive') return `player.teleport.${3 + Math.min(2, Math.floor(a.t / a.dur * 3))}`;
      if (a.type === 'clear') return `player.clear.${Math.min(3, Math.floor(a.t / 1000 * A.clearFps))}`;
      if (a.type === 'torch' || a.type === 'key' || a.type === 'door' || a.type === 'tpActivate') {
        const f = Math.min(2, Math.floor(a.t / 1000 * A.interactFps));
        return `player.interact.${p.dir}.${f}`;
      }
    }
    if (p.moving) return `player.walk.${p.dir}.${Math.floor(p.walkT) % 6}`;
    return `player.idle.${p.dir}.${Math.floor(p.idleT * A.idleFps) % 4}`;
  }

  _drawPlayer(ctx, g, time, ox, oy, tp) {
    const p = g.player;
    const name = this._playerFrame(g, time);
    const flip = p.flip && name.includes('side');
    const px = Math.round(ox + p.x * tp - tp / 2);
    const py = Math.round(oy + (p.y + 0.35) * tp - tp);
    this.sprites.draw(ctx, name, px, py, tp, tp, flip);
  }

  _drawAboveDark(ctx, g, time, ox, oy, tp) {
    const S = this.sprites;
    const W = g.W;
    const p = g.player;
    // 꺼진 횃불은 시선이 닿으면 어둠 속에서도 희미하게 보인다
    ctx.globalAlpha = 0.35;
    g.torches.forEach((t, i) => {
      if (g.torchLit[i] || !this._inView(t.x, t.y)) return;
      if (!g.los[t.y * W + t.x]) return;
      const side = t.wall !== 'N';
      let px = ox + (t.x + t.dx) * tp;
      let py = oy + (t.y + t.dy) * tp;
      if (t.wall === 'E') px -= tp * 0.5;
      if (t.wall === 'W') px += tp * 0.5;
      if (t.wall === 'S') py -= tp * 0.55;
      S.draw(ctx, side ? 'torch.side.off' : 'torch.off', px, py, tp, tp, t.wall === 'W');
    });
    ctx.globalAlpha = 1;
    // 열쇠는 시야 밖이어도 6칸 이내면 작게 반짝인다
    ctx.globalCompositeOperation = 'lighter';
    g.keys.forEach((k, i) => {
      if (g.keyState[i] !== 0) return;
      const d = Math.hypot(k.x + 0.5 - p.x, k.y + 0.5 - p.y);
      if (d > CONFIG.keySparkleRadius) return;
      const phase = (time * 1.3 + i * 0.37) % 1;
      if (phase > 0.55) return;
      const f = Math.min(3, Math.floor(phase / 0.55 * 4));
      ctx.globalAlpha = 0.9;
      S.draw(ctx, `fx.sparkle.${k.color}.${f}`, ox + k.x * tp, oy + k.y * tp - tp * 0.15, tp, tp);
    });
    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = 'source-over';
  }
}

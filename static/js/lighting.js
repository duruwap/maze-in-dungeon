// 조명: 화면 크기 어둠 레이어에서, 시야 계산으로 보이는 칸만 방사형 그라데이션으로 지운다.
// 벽 너머는 절대 보이지 않도록 모든 빛은 (광원 조명 칸 ∩ 플레이어 시선 칸) 경로로 클립한다.
import { CONFIG } from './config.js';

export class Lighting {
  constructor() {
    this.canvas = document.createElement('canvas');
    this.ctx = this.canvas.getContext('2d');
    this.res = CONFIG.lightResolution;
    this.playerPath = null;
    this.torchPaths = new Map();
    this.cacheKey = '';
  }

  resize(w, h) {
    this.canvas.width = Math.max(1, Math.round(w * this.res));
    this.canvas.height = Math.max(1, Math.round(h * this.res));
    this.w = w;
    this.h = h;
  }

  _rebuild(g) {
    const key = `${g.losVersion}:${g.lightVersion}:${g.doorOpen}`;
    if (key === this.cacheKey) return;
    this.cacheKey = key;
    const W = g.W;
    const p = new Path2D();
    for (const i of g.losList) p.rect(i % W, (i / W) | 0, 1, 1);
    this.playerPath = p;
    this.torchPaths.clear();
    g.torches.forEach((t, ti) => {
      if (!g.torchLit[ti] || !g.torchLight[ti]) return;
      const path = new Path2D();
      let any = false;
      for (const i of g.torchLight[ti]) {
        if (g.los[i]) { path.rect(i % W, (i / W) | 0, 1, 1); any = true; }
      }
      if (any) this.torchPaths.set(ti, path);
    });
  }

  render(mainCtx, g, o) {
    this._rebuild(g);
    const ctx = this.ctx;
    const r = this.res;
    const tp = o.tp * r;
    const ox = o.ox * r;
    const oy = o.oy * r;
    const cw = this.canvas.width;
    const ch = this.canvas.height;
    const p = g.player;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.globalCompositeOperation = 'source-over';
    ctx.globalAlpha = 1;
    ctx.clearRect(0, 0, cw, ch);
    ctx.fillStyle = `rgb(${o.dark[0]},${o.dark[1]},${o.dark[2]})`;
    ctx.fillRect(0, 0, cw, ch);

    ctx.globalCompositeOperation = 'destination-out';
    // 월드 좌표(칸) 변환
    ctx.setTransform(tp, 0, 0, tp, ox, oy);

    // 플레이어 램프
    const R = g.visionR;
    ctx.save();
    ctx.clip(this.playerPath);
    let gr = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, R + 0.5);
    gr.addColorStop(0, 'rgba(0,0,0,1)');
    gr.addColorStop(0.55, 'rgba(0,0,0,0.97)');
    gr.addColorStop(0.8, 'rgba(0,0,0,0.6)');
    gr.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = gr;
    ctx.fillRect(p.x - R - 1, p.y - R - 1, R * 2 + 2, R * 2 + 2);
    ctx.restore();

    // 횃불
    const TR = CONFIG.torch.radius;
    const vx0 = -ox / tp - TR - 1;
    const vy0 = -oy / tp - TR - 1;
    const vx1 = (cw - ox) / tp + TR + 1;
    const vy1 = (ch - oy) / tp + TR + 1;
    const lights = [];
    for (const [ti, path] of this.torchPaths) {
      const t = g.torches[ti];
      if (t.ix < vx0 || t.ix > vx1 || t.iy < vy0 || t.iy > vy1) continue;
      const fl = o.flicker
        ? 1 + CONFIG.torch.flicker * (Math.sin(o.time * 9.1 + ti * 2.3) * 0.6 + Math.sin(o.time * 23.7 + ti) * 0.4)
        : 1;
      const rad = (TR + 0.5) * fl;
      lights.push([t, path, rad]);
      ctx.save();
      ctx.clip(path);
      gr = ctx.createRadialGradient(t.ix, t.iy, 0, t.ix, t.iy, rad);
      gr.addColorStop(0, 'rgba(0,0,0,1)');
      gr.addColorStop(0.5, 'rgba(0,0,0,0.92)');
      gr.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.fillStyle = gr;
      ctx.fillRect(t.ix - rad, t.iy - rad, rad * 2, rad * 2);
      ctx.restore();
    }
    ctx.setTransform(1, 0, 0, 1, 0, 0);

    mainCtx.globalCompositeOperation = 'source-over';
    mainCtx.globalAlpha = o.darkAlpha;
    mainCtx.imageSmoothingEnabled = true;
    mainCtx.drawImage(this.canvas, 0, 0, o.W, o.H);
    mainCtx.imageSmoothingEnabled = false;
    mainCtx.globalAlpha = 1;

    // 따뜻한 빛 번짐 (lighter)
    mainCtx.globalCompositeOperation = 'lighter';
    mainCtx.setTransform(o.tp, 0, 0, o.tp, o.ox, o.oy);
    for (const [t, path, rad] of lights) {
      mainCtx.save();
      mainCtx.clip(path);
      const g2 = mainCtx.createRadialGradient(t.ix, t.iy, 0, t.ix, t.iy, rad);
      g2.addColorStop(0, 'rgba(255,179,71,0.30)');
      g2.addColorStop(0.4, 'rgba(255,140,50,0.12)');
      g2.addColorStop(1, 'rgba(255,120,40,0)');
      mainCtx.fillStyle = g2;
      mainCtx.fillRect(t.ix - rad, t.iy - rad, rad * 2, rad * 2);
      mainCtx.restore();
    }
    // 램프: 약한 노란빛
    mainCtx.save();
    mainCtx.clip(this.playerPath);
    const lg = mainCtx.createRadialGradient(p.x, p.y - 0.2, 0, p.x, p.y - 0.2, R);
    lg.addColorStop(0, 'rgba(255,224,138,0.16)');
    lg.addColorStop(1, 'rgba(255,224,138,0)');
    mainCtx.fillStyle = lg;
    mainCtx.fillRect(p.x - R, p.y - R, R * 2, R * 2);
    mainCtx.restore();
    mainCtx.setTransform(1, 0, 0, 1, 0, 0);
    mainCtx.globalCompositeOperation = 'source-over';
  }
}

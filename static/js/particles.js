// 파티클 풀: 횃불 불똥, 공기 중 먼지, 발밑 먼지, 열쇠 빛 조각, 텔레포트 청록 입자.
// 객체를 재사용해 매 프레임 할당을 피하고, 저사양이면 개수를 자동으로 줄인다.
import { CONFIG } from './config.js';

const COLORS = {
  ember: ['#FFE08A', '#FFB347', '#E0662C'],
  dust: ['#8E97B8', '#6A7396'],
  foot: ['#6A6478', '#4C485A'],
  teal: ['#B8FFF4', '#48E0D0', '#1F8A8A'],
  red: ['#FFD2C8', '#E0413A'],
  blue: ['#D2E4FF', '#3F7FE0'],
  green: ['#D8FFD0', '#4CC25A'],
  yellow: ['#FFF6D0', '#F2D03B'],
  gold: ['#FFF6D0', '#FFE08A', '#FFB347'],
};

export class Particles {
  constructor() {
    this.pool = [];
    for (let i = 0; i < CONFIG.particles.max; i++) {
      this.pool.push({ alive: false, x: 0, y: 0, vx: 0, vy: 0, g: 0, life: 0, max: 1, c: '', size: 1, layer: 'under', glow: false });
    }
    this.budget = CONFIG.particles.max;
    this.ambientT = 0;
    this.lowT = 0;
  }

  clear() {
    for (const p of this.pool) p.alive = false;
  }

  spawn(x, y, vx, vy, life, kind, opts = {}) {
    let alive = 0;
    let slot = null;
    for (const p of this.pool) {
      if (p.alive) alive++;
      else if (!slot) slot = p;
    }
    if (!slot || alive >= this.budget) return;
    const cols = COLORS[kind] || COLORS.dust;
    slot.alive = true;
    slot.x = x; slot.y = y; slot.vx = vx; slot.vy = vy;
    slot.g = opts.g || 0;
    slot.life = 0; slot.max = life;
    slot.c = cols[(Math.random() * cols.length) | 0];
    slot.size = opts.size || 1;
    slot.layer = opts.layer || 'under';
    slot.glow = !!opts.glow;
    slot.fade = opts.fade !== false;
  }

  burst(x, y, kind, n, speed, life, opts = {}) {
    for (let i = 0; i < n; i++) {
      const a = Math.random() * Math.PI * 2;
      const s = speed * (0.4 + Math.random() * 0.6);
      this.spawn(x, y, Math.cos(a) * s, Math.sin(a) * s + (opts.up || 0), life * (0.6 + Math.random() * 0.5), kind, opts);
    }
  }

  /** fps: 최근 평균 FPS. 45 미만이 지속되면 예산을 줄인다 */
  update(dt, game, fps) {
    if (fps < CONFIG.particles.lowFps) this.lowT += dt; else this.lowT = Math.max(0, this.lowT - dt * 0.5);
    if (this.lowT > CONFIG.particles.lowFpsSeconds && this.budget > 60) {
      this.budget = Math.max(60, Math.floor(this.budget / 2));
      this.lowT = 0;
    }
    for (const p of this.pool) {
      if (!p.alive) continue;
      p.life += dt;
      if (p.life >= p.max) { p.alive = false; continue; }
      p.vy += p.g * dt;
      p.x += p.vx * dt;
      p.y += p.vy * dt;
    }
    if (!game || game.paused) return;
    // 주변 효과: 켜진 횃불 불똥 + 공기 중 먼지
    this.ambientT += dt;
    const rate = this.budget / CONFIG.particles.max;
    while (this.ambientT > 0.05) {
      this.ambientT -= 0.05;
      const pl = game.player;
      if (Math.random() < 0.5 * rate) {
        this.spawn(pl.x + (Math.random() - 0.5) * 8, pl.y + (Math.random() - 0.5) * 6,
          (Math.random() - 0.5) * 0.15, (Math.random() - 0.5) * 0.1, 3 + Math.random() * 2, 'dust', { layer: 'under' });
      }
      for (let i = 0; i < game.torches.length; i++) {
        if (!game.torchLit[i]) continue;
        const t = game.torches[i];
        if (Math.abs(t.ix - pl.x) > 10 || Math.abs(t.iy - pl.y) > 8) continue;
        if (Math.random() < 0.18 * rate) {
          const fx = t.x + 0.5 + t.dx * 0.5;
          const fy = t.y + 0.5 + t.dy * 0.5 - (t.wall === 'N' ? 0.6 : 0.3);
          this.spawn(fx + (Math.random() - 0.5) * 0.15, fy, (Math.random() - 0.5) * 0.3, -0.6 - Math.random() * 0.6,
            0.6 + Math.random() * 0.6, 'ember', { layer: 'over', glow: true });
        }
      }
    }
  }

  draw(ctx, ox, oy, tp, layer, game) {
    const px = tp / CONFIG.tile;
    const W = game.W;
    for (const p of this.pool) {
      if (!p.alive || p.layer !== layer) continue;
      if (layer === 'over') {
        const tx = p.x | 0;
        const ty = p.y | 0;
        if (tx < 0 || ty < 0 || tx >= W || ty >= game.H || !game.los[ty * W + tx]) continue;
      }
      const k = p.life / p.max;
      ctx.globalAlpha = p.fade ? Math.max(0, 1 - k * k) : 1;
      ctx.globalCompositeOperation = p.glow ? 'lighter' : 'source-over';
      ctx.fillStyle = p.c;
      const s = Math.max(1, Math.round(p.size * px));
      ctx.fillRect(Math.round(ox + p.x * tp - s / 2), Math.round(oy + p.y * tp - s / 2), s, s);
    }
    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = 'source-over';
  }
}

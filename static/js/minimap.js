// 미니맵: 시야에 들어온 칸(벽 포함)을 자동 기록. 지나간 칸은 밝게, 보기만 한 칸은 어둡게.
import { CONFIG } from './config.js';
import { T_WALL, T_EXIT, T_DOOR } from './game.js';

function hex(c) {
  const n = parseInt(c.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

export class Minimap {
  constructor(sprites) {
    this.sprites = sprites;
    this.base = document.createElement('canvas');
    this.bctx = this.base.getContext('2d');
    this.colors = {
      wall: hex(CONFIG.palette.mapWall),
      seen: hex(CONFIG.palette.mapSeen),
      visited: hex(CONFIG.palette.mapVisited),
      exit: hex(CONFIG.palette.mapExit),
    };
  }

  setGame(game) {
    this.game = game;
    this.base.width = game.W;
    this.base.height = game.H;
    this.img = this.bctx.createImageData(game.W, game.H);
    this.redrawAll();
  }

  _paint(i) {
    const g = this.game;
    const d = this.img.data;
    const s = g.seen[i];
    let c = null;
    if (s) {
      const t = g.tiles[i];
      if (t === T_WALL) c = this.colors.wall;
      else if (t === T_EXIT || t === T_DOOR) c = this.colors.exit;
      else c = s === 2 ? this.colors.visited : this.colors.seen;
    }
    const o = i * 4;
    if (c) { d[o] = c[0]; d[o + 1] = c[1]; d[o + 2] = c[2]; d[o + 3] = 255; } else { d[o + 3] = 0; }
  }

  redrawAll() {
    const g = this.game;
    for (let i = 0; i < g.W * g.H; i++) this._paint(i);
    this.bctx.putImageData(this.img, 0, 0);
    g.newlySeen = [];
    g.minimapFull = false;
  }

  update() {
    const g = this.game;
    if (!g) return;
    if (g.minimapFull) { this.redrawAll(); return; }
    if (!g.newlySeen.length) return;
    for (const i of g.newlySeen) this._paint(i);
    g.newlySeen = [];
    this.bctx.putImageData(this.img, 0, 0);
  }

  /**
   * 지도를 (x,y,w,h) 영역에 맞춰 그린다.
   * opts.big: 전체 지도, opts.tpSel: 텔레포트 선택 상태
   * 반환: 칸 → 화면 좌표 변환 정보 (터치 선택용)
   */
  draw(ctx, x, y, w, h, opts = {}) {
    const g = this.game;
    if (!g) return null;
    const cell = Math.max(1, Math.floor(Math.min(w / g.W, h / g.H)));
    const mw = cell * g.W;
    const mh = cell * g.H;
    const mx = Math.round(x + (w - mw) / 2);
    const my = Math.round(y + (h - mh) / 2);
    ctx.imageSmoothingEnabled = false;
    ctx.fillStyle = 'rgba(5,6,12,0.92)';
    ctx.fillRect(mx - cell, my - cell, mw + cell * 2, mh + cell * 2);
    ctx.drawImage(this.base, mx, my, mw, mh);
    const S = this.sprites;
    const W = g.W;
    const ic = Math.max(opts.big ? 14 : 8, Math.round(cell * (opts.big ? 1.6 : 2.2)));
    const icon = (name, tx, ty, size = ic) => {
      S.draw(ctx, name, Math.round(mx + (tx + 0.5) * cell - size / 2), Math.round(my + (ty + 0.5) * cell - size / 2), size, size);
    };
    // 탈출 방
    const e = g.maze.exit;
    if (g.seen[e.y * W + e.x] || g.seen[g.maze.door.y * W + g.maze.door.x] || g.seen[(g.maze.door.y + 1) * W + g.maze.door.x]) {
      icon('icon.exit', e.x, e.y, ic * 1.2);
    }
    g.torches.forEach((t, i) => { if (g.torchLit[i]) icon('icon.torch', t.x, t.y, ic * 0.8); });
    g.teleports.forEach((t, i) => {
      if (!g.seen[t.y * W + t.x]) return;
      icon(g.tpActive[i] ? 'icon.tp_on' : 'icon.tp_off', t.x, t.y);
    });
    g.keys.forEach((k, i) => {
      if (g.keyState[i] === 0 && g.seen[k.y * W + k.x]) icon(`icon.key.${k.color}`, k.x, k.y);
    });
    // 텔레포트 선택 강조
    if (opts.tpSel) {
      const t = g.teleports[opts.tpSel.sel];
      const pulse = 0.6 + 0.4 * Math.sin(performance.now() / 150);
      ctx.strokeStyle = `rgba(184,255,244,${pulse})`;
      ctx.lineWidth = Math.max(2, cell * 0.4);
      const r = ic * 0.9;
      ctx.strokeRect(Math.round(mx + (t.x + 0.5) * cell - r), Math.round(my + (t.y + 0.5) * cell - r), r * 2, r * 2);
    }
    // 내 위치 (방향 화살표)
    const p = g.player;
    const ang = Math.atan2(p.fy, p.fx);
    const dir = Math.round(((ang + Math.PI * 2) % (Math.PI * 2)) / (Math.PI / 4)) % 8;
    const size = ic * 1.1;
    S.draw(ctx, `icon.player.${dir}`, Math.round(mx + p.x * cell - size / 2), Math.round(my + p.y * cell - size / 2), size, size);
    return { mx, my, cell };
  }
}

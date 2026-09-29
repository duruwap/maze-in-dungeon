// 게임 상태와 규칙 (렌더링과 분리). 좌표 단위는 칸, 칸 (x,y)는 [x,x+1)×[y,y+1).
import { CONFIG } from './config.js';
import { shadowcast } from './fov.js';
import { bytesToB64, b64ToBytes } from './storage.js';

export const T_WALL = 0;
export const T_CORR = 1;
export const T_ROOM = 2;
export const T_EXIT = 3;
export const T_DOOR = 4;
const CHAR_TO_T = { '#': T_WALL, '.': T_CORR, R: T_ROOM, E: T_EXIT, D: T_DOOR };
const WALL_DIR = { N: [0, -1], S: [0, 1], E: [1, 0], W: [-1, 0] };

export class Game {
  constructor(maze, { resumed = false } = {}) {
    this.maze = maze;
    const W = (this.W = maze.width);
    const H = (this.H = maze.height);
    this.tiles = new Uint8Array(W * H);
    this.floorCount = 0;
    maze.tiles.forEach((row, y) => {
      for (let x = 0; x < W; x++) {
        const t = CHAR_TO_T[row[x]];
        this.tiles[y * W + x] = t;
        if (t === T_CORR || t === T_ROOM || t === T_EXIT) this.floorCount++;
      }
    });
    this.keys = maze.keys;
    this.totalKeys = maze.keys.length;
    this.torches = maze.torches.map((t) => {
      const [dx, dy] = WALL_DIR[t.wall];
      return { ...t, dx, dy, ix: t.x + 0.5 + dx * 0.42, iy: t.y + 0.5 + dy * 0.42 };
    });
    this.teleports = maze.teleports;

    const s = maze.start;
    this.player = {
      x: s.x + 0.5, y: s.y + 0.5, fx: 0, fy: 1,
      dir: 'down', flip: false, moving: false, speed: 0,
      walkT: 0, idleT: 0, lastStepFrame: -1,
    };
    this.action = null;
    this.mode = 'play';       // play | map | tpselect | done
    this.paused = false;
    this.started = false;
    this.finished = false;
    this.elapsed = 0;
    this.resumed = resumed;
    this.teleportsUsed = 0;

    this.torchLit = new Uint8Array(this.torches.length);
    this.tpActive = new Uint8Array(this.teleports.map((t) => (t.active ? 1 : 0)));
    this.keyState = new Uint8Array(this.totalKeys); // 0 바닥, 1 소지, 2 자물쇠에 꽂음
    this.doorOpen = false;
    this.doorAnim = 0;       // 0..1 열림 연출

    this.seen = new Uint8Array(W * H);   // 0 미발견, 1 봄, 2 지나감
    this.newlySeen = [];
    this.los = new Uint8Array(W * H);
    this.losList = [];
    this.losTile = -1;
    this.losDirty = true;
    this.losVersion = 0;
    this.litMask = new Uint8Array(W * H);
    this.torchLight = this.torches.map(() => null);
    this.lightVersion = 0;

    this.visionR = CONFIG.vision.base;
    this.target = null;
    this.tpSel = null;
    this.status = null;       // {key, params, until}
    this.fx = [];             // 오디오/파티클용 이벤트
    this.clock = 0;           // 실제 흐른 시간(애니메이션용, 초)
    this._opaque = (x, y) => this.opaque(x, y);
  }

  // ---------- 지형 ----------
  tileAt(x, y) {
    if (x < 0 || y < 0 || x >= this.W || y >= this.H) return T_WALL;
    return this.tiles[y * this.W + x];
  }

  solidAt(x, y) {
    const t = this.tileAt(x, y);
    return t === T_WALL || (t === T_DOOR && !this.doorOpen);
  }

  opaque(x, y) {
    return this.solidAt(x, y);
  }

  _boxHits(x, y) {
    const h = CONFIG.hitbox / 2;
    const x0 = Math.floor(x - h);
    const x1 = Math.floor(x + h - 1e-6);
    const y0 = Math.floor(y - h);
    const y1 = Math.floor(y + h - 1e-6);
    for (let ty = y0; ty <= y1; ty++) {
      for (let tx = x0; tx <= x1; tx++) {
        if (this.solidAt(tx, ty)) return true;
      }
    }
    return false;
  }

  _moveAxis(d, axis) {
    const p = this.player;
    const h = CONFIG.hitbox / 2;
    const eps = 1e-4;
    const nx = axis === 0 ? p.x + d : p.x;
    const ny = axis === 1 ? p.y + d : p.y;
    if (!this._boxHits(nx, ny)) {
      p.x = nx;
      p.y = ny;
      return;
    }
    // 벽에 붙이기
    if (axis === 0) {
      p.x = d > 0 ? Math.max(p.x, Math.floor(nx + h) - h - eps) : Math.min(p.x, Math.floor(nx - h) + 1 + h + eps);
    } else {
      p.y = d > 0 ? Math.max(p.y, Math.floor(ny + h) - h - eps) : Math.min(p.y, Math.floor(ny - h) + 1 + h + eps);
    }
    // 모서리 보정: 한쪽 칸만 막혔고 조금만 걸쳤으면 열린 쪽으로 미끄러뜨린다
    const assist = CONFIG.cornerAssist;
    const step = Math.abs(d);
    if (axis === 0) {
      const col = d > 0 ? Math.floor(nx + h) : Math.floor(nx - h);
      const r0 = Math.floor(p.y - h);
      const r1 = Math.floor(p.y + h - eps);
      if (r0 === r1) return;
      const b0 = this.solidAt(col, r0);
      const b1 = this.solidAt(col, r1);
      if (b0 && !b1) {
        const ov = r0 + 1 - (p.y - h);
        if (ov < assist) { const s = Math.min(ov + eps, step); if (!this._boxHits(p.x, p.y + s)) p.y += s; }
      } else if (!b0 && b1) {
        const ov = p.y + h - r1;
        if (ov < assist) { const s = Math.min(ov + eps, step); if (!this._boxHits(p.x, p.y - s)) p.y -= s; }
      }
    } else {
      const row = d > 0 ? Math.floor(ny + h) : Math.floor(ny - h);
      const c0 = Math.floor(p.x - h);
      const c1 = Math.floor(p.x + h - eps);
      if (c0 === c1) return;
      const b0 = this.solidAt(c0, row);
      const b1 = this.solidAt(c1, row);
      if (b0 && !b1) {
        const ov = c0 + 1 - (p.x - h);
        if (ov < assist) { const s = Math.min(ov + eps, step); if (!this._boxHits(p.x + s, p.y)) p.x += s; }
      } else if (!b0 && b1) {
        const ov = p.x + h - c1;
        if (ov < assist) { const s = Math.min(ov + eps, step); if (!this._boxHits(p.x - s, p.y)) p.x -= s; }
      }
    }
  }

  // ---------- 조명/시야 ----------
  litTorchCount() {
    let n = 0;
    for (let i = 0; i < this.torchLit.length; i++) n += this.torchLit[i];
    return n;
  }

  targetVision() {
    const v = CONFIG.vision;
    const adapt = Math.min(v.adaptMax, v.base + v.adaptStep * Math.floor(this.elapsed / 1000 / v.adaptEvery));
    return adapt + Math.min(v.torchBonusMax, v.perTorch * this.litTorchCount());
  }

  _computeTorchLight(i) {
    const t = this.torches[i];
    const W = this.W;
    const tiles = [];
    const R = CONFIG.torch.radius;
    shadowcast(this._opaque, t.x, t.y, R + 0.5, (x, y) => {
      if (x < 0 || y < 0 || x >= W || y >= this.H) return;
      const idx = y * W + x;
      tiles.push(idx);
      this.litMask[idx] = 1;
    });
    this.torchLight[i] = tiles;
    this.lightVersion++;
  }

  _recomputeAllTorchLight() {
    this.litMask.fill(0);
    for (let i = 0; i < this.torches.length; i++) {
      if (this.torchLit[i]) this._computeTorchLight(i);
    }
  }

  _updateVisibility() {
    const p = this.player;
    const W = this.W;
    const tx = Math.floor(p.x);
    const ty = Math.floor(p.y);
    const ti = ty * W + tx;
    if (ti !== this.losTile || this.losDirty) {
      for (const i of this.losList) this.los[i] = 0;
      this.losList = [];
      shadowcast(this._opaque, tx, ty, CONFIG.vision.losRadius, (x, y) => {
        if (x < 0 || y < 0 || x >= W || y >= this.H) return;
        const i = y * W + x;
        if (!this.los[i]) {
          this.los[i] = 1;
          this.losList.push(i);
        }
      });
      this.losTile = ti;
      this.losDirty = false;
      this.losVersion++;
    }
    const r = this.visionR + 0.35;
    const r2 = r * r;
    for (const i of this.losList) {
      if (this.seen[i]) continue;
      const dx = (i % W) + 0.5 - p.x;
      const dy = ((i / W) | 0) + 0.5 - p.y;
      if (dx * dx + dy * dy <= r2 || this.litMask[i]) {
        this.seen[i] = 1;
        this.newlySeen.push(i);
      }
    }
    if (this.seen[ti] !== 2) {
      this.seen[ti] = 2;
      this.newlySeen.push(ti);
    }
  }

  isVisible(i) {
    return this.los[i] === 1;
  }

  // ---------- 상호작용 ----------
  _findTarget() {
    if (this.action || this.mode !== 'play') return null;
    const p = this.player;
    const W = this.W;
    const reach = CONFIG.interact.reach;
    const bias = CONFIG.interact.facingBias;
    let best = null;
    let bestScore = Infinity;
    const consider = (type, id, x, y, maxD) => {
      const dx = x - p.x;
      const dy = y - p.y;
      const d = Math.hypot(dx, dy);
      if (d > maxD) return;
      const dot = d > 0.01 ? (dx * p.fx + dy * p.fy) / d : 1;
      const score = d - bias * dot;
      if (score < bestScore) {
        bestScore = score;
        best = { type, id };
      }
    };
    this.torches.forEach((t, i) => {
      if (!this.torchLit[i] && this.los[t.y * W + t.x]) consider('torch', i, t.ix, t.iy, reach);
    });
    this.keys.forEach((k, i) => {
      if (this.keyState[i] === 0 && this.los[k.y * W + k.x]) consider('key', i, k.x + 0.5, k.y + 0.5, reach);
    });
    this.teleports.forEach((t, i) => {
      const d = Math.hypot(t.x + 0.5 - p.x, t.y + 0.5 - p.y);
      if (d <= CONFIG.interact.standOn) {
        const type = this.tpActive[i] ? 'tpUse' : 'tpActivate';
        if (d - bias < bestScore) { bestScore = d - bias; best = { type, id: i }; }
      }
    });
    if (!this.doorOpen) {
      const d = this.maze.door;
      consider('door', 0, d.x + 0.5, d.y + 0.9, reach);
    }
    return best;
  }

  _emit(type, data = {}) {
    this.fx.push({ type, ...data });
  }

  _setStatus(key, params, ms = CONFIG.statusMs) {
    this.status = { key, params, until: this.clock + ms / 1000 };
  }

  heldKeys() {
    const out = [];
    for (let i = 0; i < this.totalKeys; i++) if (this.keyState[i] === 1) out.push(i);
    return out;
  }

  collectedCount() {
    let n = 0;
    for (let i = 0; i < this.totalKeys; i++) if (this.keyState[i] >= 1) n++;
    return n;
  }

  insertedCount() {
    let n = 0;
    for (let i = 0; i < this.totalKeys; i++) if (this.keyState[i] === 2) n++;
    return n;
  }

  _startAction(type, dur, data = {}) {
    this.action = { type, t: 0, dur, ...data };
  }

  interact() {
    if (this.paused) return;
    if (this.mode === 'tpselect') { this.confirmTeleport(); return; }
    if (this.mode !== 'play' || this.action || !this.target) return;
    const { type, id } = this.target;
    const p = this.player;
    const face = (x, y) => this._face(x - p.x, y - p.y);
    if (type === 'torch') {
      const t = this.torches[id];
      face(t.ix, t.iy);
      this._startAction('torch', CONFIG.torch.lightMs, { id });
      this._emit('torch_start', { x: t.ix, y: t.iy });
    } else if (type === 'key') {
      const k = this.keys[id];
      face(k.x + 0.5, k.y + 0.5);
      this.keyState[id] = 1;
      this._startAction('key', CONFIG.interact.keyAnimMs, { id });
      this._emit('key', { id, color: k.color, x: k.x + 0.5, y: k.y + 0.5, collected: this.collectedCount() });
      if (this.collectedCount() === this.totalKeys) this._emit('all_keys');
    } else if (type === 'tpActivate') {
      const t = this.teleports[id];
      this._startAction('tpActivate', CONFIG.teleport.activateMs, { id });
      this._emit('tp_charge', { x: t.x + 0.5, y: t.y + 0.5 });
    } else if (type === 'tpUse') {
      this.openTeleportSelect(id);
    } else if (type === 'door') {
      const d = this.maze.door;
      face(d.x + 0.5, d.y + 0.5);
      const held = this.heldKeys();
      if (!held.length) {
        this._setStatus('status.keys_needed', { have: this.collectedCount(), total: this.totalKeys });
        this._emit('denied');
        return;
      }
      this._startAction('door', CONFIG.door.unlockMs, { keys: held, inserted: 0 });
    }
  }

  _face(dx, dy) {
    const p = this.player;
    const l = Math.hypot(dx, dy);
    if (l < 1e-3) return;
    p.fx = dx / l;
    p.fy = dy / l;
    if (Math.abs(dx) > Math.abs(dy)) {
      p.dir = 'side';
      p.flip = dx < 0;
    } else {
      p.dir = dy < 0 ? 'up' : 'down';
    }
  }

  _finishAction() {
    const a = this.action;
    this.action = null;
    if (a.type === 'torch') {
      this.torchLit[a.id] = 1;
      this._computeTorchLight(a.id);
      const t = this.torches[a.id];
      this._emit('torch_lit', { id: a.id, x: t.ix, y: t.iy });
    } else if (a.type === 'tpActivate') {
      this.tpActive[a.id] = 1;
      const t = this.teleports[a.id];
      this._emit('tp_active', { id: a.id, x: t.x + 0.5, y: t.y + 0.5 });
      this._setStatus('status.teleport_on', null, CONFIG.toastMs);
    } else if (a.type === 'door') {
      for (const k of a.keys) this.keyState[k] = 2;
      if (this.insertedCount() === this.totalKeys) {
        this._startAction('doorOpen', CONFIG.door.openMs);
        this._emit('door_open');
      } else {
        this._setStatus('status.keys_inserted', { have: this.insertedCount(), total: this.totalKeys });
      }
    } else if (a.type === 'doorOpen') {
      this.doorOpen = true;
      this.doorAnim = 1;
      this.losDirty = true;
      this._recomputeAllTorchLight();
    } else if (a.type === 'teleport') {
      const t = this.teleports[a.to];
      this.player.x = t.x + 0.5;
      this.player.y = t.y + 0.5;
      this.player.dir = 'down';
      this.losDirty = true;
      this.teleportsUsed++;
      this._startAction('arrive', CONFIG.teleport.arriveMs, { to: a.to });
      this._emit('tp_arrive', { x: t.x + 0.5, y: t.y + 0.5 });
    }
  }

  // ---------- 텔레포트 선택 ----------
  openTeleportSelect(fromId) {
    const options = [];
    this.teleports.forEach((t, i) => { if (this.tpActive[i]) options.push(i); });
    this.mode = 'tpselect';
    this.tpSel = { from: fromId, options, sel: fromId };
    this._emit('ui_open');
  }

  moveTeleportSelection(dir) {
    if (!this.tpSel) return;
    const [vx, vy] = { up: [0, -1], down: [0, 1], left: [-1, 0], right: [1, 0] }[dir];
    const cur = this.teleports[this.tpSel.sel];
    let best = null;
    let bestScore = Infinity;
    for (const i of this.tpSel.options) {
      if (i === this.tpSel.sel) continue;
      const t = this.teleports[i];
      const dx = t.x - cur.x;
      const dy = t.y - cur.y;
      const along = dx * vx + dy * vy;
      if (along <= 0) continue;
      const across = Math.abs(dx * vy - dy * vx);
      const score = along + across * 2;
      if (score < bestScore) { bestScore = score; best = i; }
    }
    if (best == null) {
      // 그 방향에 없으면 목록 순서로 순환
      const idx = this.tpSel.options.indexOf(this.tpSel.sel);
      const step = dir === 'up' || dir === 'left' ? -1 : 1;
      const n = this.tpSel.options.length;
      best = this.tpSel.options[(idx + step + n) % n];
    }
    this.tpSel.sel = best;
    this._emit('ui_move');
  }

  selectTeleport(id) {
    if (this.tpSel && this.tpSel.options.includes(id)) this.tpSel.sel = id;
  }

  confirmTeleport() {
    if (!this.tpSel) return;
    const { from, sel } = this.tpSel;
    this.tpSel = null;
    this.mode = 'play';
    if (sel === from) return;
    const t = this.teleports[from];
    this._startAction('teleport', CONFIG.teleport.travelMs, { from, to: sel });
    this._emit('tp_depart', { x: t.x + 0.5, y: t.y + 0.5 });
  }

  cancelOverlay() {
    if (this.mode === 'tpselect') { this.tpSel = null; this.mode = 'play'; return true; }
    if (this.mode === 'map') { this.mode = 'play'; return true; }
    return false;
  }

  toggleMap() {
    if (this.mode === 'play') this.mode = 'map';
    else if (this.mode === 'map') this.mode = 'play';
  }

  // ---------- 프레임 갱신 ----------
  update(dt, move) {
    this.clock += dt;
    if (this.paused) return;
    if (this.started && !this.finished) this.elapsed += dt * 1000;

    const tv = this.targetVision();
    const k = Math.min(1, dt * CONFIG.vision.lerp);
    this.visionR += (tv - this.visionR) * k;

    if (this.action) {
      this.action.t += dt * 1000;
      const a = this.action;
      if (a.type === 'door') {
        // 열쇠를 하나씩 꽂는 소리
        const n = Math.min(a.keys.length, Math.floor(a.t / (a.dur / a.keys.length)) + 1);
        while (a.inserted < n) {
          const kid = a.keys[a.inserted++];
          this._emit('lock', { color: this.keys[kid].color, n: this.insertedCount() + a.inserted });
        }
      }
      if (a.type === 'doorOpen') this.doorAnim = Math.min(1, a.t / a.dur);
      if (a.t >= a.dur) this._finishAction();
    }

    const p = this.player;
    let mx = 0;
    let my = 0;
    if (this.mode === 'play' && !this.action && !this.finished) {
      [mx, my] = move;
    }
    const mag = Math.hypot(mx, my);
    if (mag > 0.01) {
      if (!this.started) {
        this.started = true;
        this._emit('start');
      }
      this._face(mx, my);
      const dist = CONFIG.moveSpeed * mag * dt;
      const steps = Math.max(1, Math.ceil(dist / CONFIG.maxStep));
      for (let i = 0; i < steps; i++) {
        this._moveAxis((mx / mag) * dist / steps, 0);
        this._moveAxis((my / mag) * dist / steps, 1);
      }
      p.moving = true;
      p.speed = mag;
      const fps = CONFIG.anim.walkFpsMin + (CONFIG.anim.walkFpsMax - CONFIG.anim.walkFpsMin) * mag;
      p.walkT += dt * fps;
      const f = Math.floor(p.walkT) % 6;
      if ((f === 1 || f === 4) && f !== p.lastStepFrame) this._emit('step', { x: p.x, y: p.y + 0.3 });
      p.lastStepFrame = f;
    } else {
      p.moving = false;
      p.speed = 0;
      p.idleT += dt;
    }

    this._updateVisibility();
    this.target = this._findTarget();

    // 출구 칸에 들어서면 클리어
    if (!this.finished && this.doorOpen) {
      const e = this.maze.exit;
      if (Math.floor(p.x) === e.x && Math.floor(p.y) === e.y) {
        this.finished = true;
        this.mode = 'done';
        this._startAction('clear', 99999);
        this._emit('clear', { time: this.elapsed });
      }
    }
    if (this.status && this.clock > this.status.until) this.status = null;
  }

  // ---------- 결과 통계 ----------
  exploredRatio() {
    let n = 0;
    for (let i = 0; i < this.seen.length; i++) {
      const t = this.tiles[i];
      if (this.seen[i] && (t === T_CORR || t === T_ROOM || t === T_EXIT)) n++;
    }
    return Math.min(1, n / Math.max(1, this.floorCount));
  }

  /** 2비트/칸: 0 미발견, 1 본 벽, 2 본 바닥, 3 지나간 바닥 */
  pathPreview() {
    const n = this.W * this.H;
    const bytes = new Uint8Array(Math.ceil(n / 4));
    for (let i = 0; i < n; i++) {
      let v = 0;
      if (this.seen[i]) {
        const wall = this.tiles[i] === T_WALL;
        v = wall ? 1 : this.seen[i] === 2 ? 3 : 2;
      }
      bytes[i >> 2] |= v << (6 - 2 * (i & 3));
    }
    return bytesToB64(bytes);
  }

  // ---------- 저장/이어하기 ----------
  serialize() {
    const p = this.player;
    return {
      v: 1,
      px: p.x, py: p.y, dir: p.dir, flip: p.flip,
      elapsed: this.elapsed, started: this.started,
      torchLit: Array.from(this.torchLit),
      tpActive: Array.from(this.tpActive),
      keyState: Array.from(this.keyState),
      doorOpen: this.doorOpen,
      teleportsUsed: this.teleportsUsed,
      seen: bytesToB64(this.seen),
    };
  }

  restore(s) {
    const p = this.player;
    p.x = s.px; p.y = s.py; p.dir = s.dir || 'down'; p.flip = !!s.flip;
    this.elapsed = s.elapsed || 0;
    this.started = !!s.started;
    this.torchLit.set(s.torchLit);
    this.tpActive.set(s.tpActive);
    this.keyState.set(s.keyState);
    this.doorOpen = !!s.doorOpen;
    this.doorAnim = this.doorOpen ? 1 : 0;
    this.teleportsUsed = s.teleportsUsed || 0;
    const seen = b64ToBytes(s.seen);
    if (seen.length === this.seen.length) this.seen.set(seen);
    this._recomputeAllTorchLight();
    this.losDirty = true;
    this.newlySeen = [];
    this.minimapFull = true;
  }
}

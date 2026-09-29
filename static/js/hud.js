// 게임 HUD: 타이머, 열쇠 슬롯, 미니맵, 상호작용 안내, 상태/토스트, 첫 판 힌트.
import { CONFIG } from './config.js';
import { t, formatTime } from './i18n.js';

const $ = (id) => document.getElementById(id);

export class Hud {
  constructor(sprites, minimap) {
    this.sprites = sprites;
    this.minimap = minimap;
    this.el = $('hud');
    this.timer = $('timer');
    this.slots = $('keyslots');
    this.prompt = $('prompt');
    this.promptText = $('prompt-text');
    this.status = $('status');
    this.toastEl = $('toast');
    this.hint = $('hint');
    this.btnE = $('btn-e');
    this.mini = $('minimap');
    this.mctx = this.mini.getContext('2d');
    this.lastTimer = '';
    this.lastPrompt = '';
    this.lastStatus = '';
    this.slotState = '';
    this.toastUntil = 0;
    this.hintUntil = 0;
  }

  show(on) {
    this.el.hidden = !on;
    if (on) this.resizeMinimap();
  }

  setGame(game, firstPlay) {
    this.game = game;
    this.slotState = '';
    this.slots.innerHTML = '';
    this.slotCanvases = [];
    const dpr = Math.min(window.devicePixelRatio || 1, 3);
    for (let i = 0; i < game.totalKeys; i++) {
      const c = document.createElement('canvas');
      c.width = c.height = Math.round(32 * dpr);
      c.className = 'slot';
      this.slots.appendChild(c);
      this.slotCanvases.push(c);
    }
    this.hintUntil = firstPlay ? performance.now() + CONFIG.hintMs : 0;
    this.hint.hidden = !firstPlay;
    if (firstPlay) this.refreshHint();
    this.toastEl.classList.remove('on');
    this.resizeMinimap();
  }

  refreshHint() {
    const touch = document.body.classList.contains('touch');
    this.hint.innerHTML = '';
    const a = document.createElement('div');
    a.textContent = t(touch ? 'hint.mobile' : 'hint.pc');
    const b = document.createElement('div');
    b.textContent = this.game ? t('hint.goal', { total: this.game.totalKeys }) : '';
    this.hint.append(a, b);
  }

  resizeMinimap() {
    const r = this.mini.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 3);
    this.mini.width = Math.max(1, Math.round(r.width * dpr));
    this.mini.height = Math.max(1, Math.round(r.height * dpr));
  }

  toast(text) {
    this.toastEl.textContent = text;
    this.toastEl.classList.add('on');
    this.toastUntil = performance.now() + CONFIG.toastMs;
  }

  _promptText(g) {
    const tg = g.target;
    if (!tg) return '';
    switch (tg.type) {
      case 'torch': return t('prompt.torch');
      case 'key': return t('prompt.key');
      case 'tpActivate': return t('prompt.tp_activate');
      case 'tpUse': return t('prompt.tp_use');
      case 'door': return g.heldKeys().length ? t('prompt.door') : t('prompt.door_locked');
      default: return '';
    }
  }

  _drawSlots(g) {
    const state = Array.from(g.keyState).join(',');
    if (state === this.slotState) return;
    this.slotState = state;
    g.keys.forEach((k, i) => {
      const c = this.slotCanvases[i];
      const ctx = c.getContext('2d');
      ctx.imageSmoothingEnabled = false;
      ctx.clearRect(0, 0, c.width, c.height);
      const s = g.keyState[i];
      this.sprites.draw(ctx, s ? `ui.slot.${k.color}` : 'ui.slot.empty', 0, 0, c.width, c.height);
      c.classList.toggle('inserted', s === 2);
      c.classList.toggle('pop', s === 1);
    });
  }

  update(g, now) {
    const tm = formatTime(g.elapsed);
    if (tm !== this.lastTimer) { this.timer.textContent = tm; this.lastTimer = tm; }
    this._drawSlots(g);

    const pt = this._promptText(g);
    if (pt !== this.lastPrompt) {
      this.lastPrompt = pt;
      this.promptText.textContent = pt;
      this.prompt.classList.toggle('on', !!pt);
      this.btnE.classList.toggle('ready', !!pt);
    }
    const st = g.status ? t(g.status.key, g.status.params) : '';
    if (st !== this.lastStatus) {
      this.lastStatus = st;
      this.status.textContent = st;
      this.status.classList.toggle('on', !!st);
    }
    if (this.toastUntil && now > this.toastUntil) {
      this.toastEl.classList.remove('on');
      this.toastUntil = 0;
    }
    if (this.hintUntil && now > this.hintUntil) {
      this.hint.hidden = true;
      this.hintUntil = 0;
    }
    // 소형 미니맵
    const ctx = this.mctx;
    ctx.clearRect(0, 0, this.mini.width, this.mini.height);
    this.minimap.draw(ctx, 0, 0, this.mini.width, this.mini.height);
  }
}

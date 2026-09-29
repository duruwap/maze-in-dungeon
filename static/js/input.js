// 입력: 키보드(WASD/방향키/E/M/Esc) + 모바일 가상 조이스틱, E 버튼.
const MOVE_KEYS = {
  KeyW: [0, -1], ArrowUp: [0, -1],
  KeyS: [0, 1], ArrowDown: [0, 1],
  KeyA: [-1, 0], ArrowLeft: [-1, 0],
  KeyD: [1, 0], ArrowRight: [1, 0],
};
const DIR_NAMES = {
  KeyW: 'up', ArrowUp: 'up', KeyS: 'down', ArrowDown: 'down',
  KeyA: 'left', ArrowLeft: 'left', KeyD: 'right', ArrowRight: 'right',
};

export class Input {
  constructor() {
    this.down = new Set();
    this.events = [];
    this.joy = { active: false, id: null, ox: 0, oy: 0, x: 0, y: 0 };
    this.touchMode = false;
    this.enabled = true;
    this.onFirstInput = null;
    this._first = false;
    this._bindKeyboard();
  }

  _fireFirst() {
    if (!this._first) {
      this._first = true;
      if (this.onFirstInput) this.onFirstInput();
    }
  }

  _bindKeyboard() {
    window.addEventListener('keydown', (e) => {
      if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT')) return;
      this._fireFirst();
      const code = e.code;
      if (MOVE_KEYS[code] || code === 'Space') e.preventDefault();
      if (e.repeat) {
        if (MOVE_KEYS[code]) this.down.add(code);
        return;
      }
      this.down.add(code);
      if (DIR_NAMES[code]) this.events.push({ type: 'dir', dir: DIR_NAMES[code] });
      if (code === 'KeyE') this.events.push({ type: 'interact' });
      if (code === 'Enter' || code === 'Space') this.events.push({ type: 'confirm' });
      if (code === 'KeyM') this.events.push({ type: 'map' });
      if (code === 'Escape' || code === 'KeyP') this.events.push({ type: 'escape' });
    });
    window.addEventListener('keyup', (e) => this.down.delete(e.code));
    window.addEventListener('blur', () => this.down.clear());
  }

  /** 모바일: 화면 왼쪽 절반 어디든 누르면 조이스틱이 생긴다 */
  bindTouch(surface, joyEl, knobEl) {
    this.joyEl = joyEl;
    this.knobEl = knobEl;
    const R = 56;
    const start = (e) => {
      this._fireFirst();
      this.touchMode = true;
      document.body.classList.add('touch');
      if (!this.enabled) return;
      for (const t of e.changedTouches) {
        if (this.joy.active) break;
        if (t.clientX > window.innerWidth / 2) continue;
        this.joy = { active: true, id: t.identifier, ox: t.clientX, oy: t.clientY, x: 0, y: 0 };
        joyEl.style.left = `${t.clientX}px`;
        joyEl.style.top = `${t.clientY}px`;
        joyEl.classList.add('on');
        knobEl.style.transform = 'translate(-50%, -50%)';
        e.preventDefault();
      }
    };
    const move = (e) => {
      for (const t of e.changedTouches) {
        if (!this.joy.active || t.identifier !== this.joy.id) continue;
        let dx = t.clientX - this.joy.ox;
        let dy = t.clientY - this.joy.oy;
        const len = Math.hypot(dx, dy);
        if (len > R) { dx = dx / len * R; dy = dy / len * R; }
        this.joy.x = dx / R;
        this.joy.y = dy / R;
        knobEl.style.transform = `translate(calc(-50% + ${dx}px), calc(-50% + ${dy}px))`;
        e.preventDefault();
      }
    };
    const end = (e) => {
      for (const t of e.changedTouches) {
        if (t.identifier === this.joy.id) {
          this.joy.active = false;
          this.joy.x = this.joy.y = 0;
          joyEl.classList.remove('on');
        }
      }
    };
    surface.addEventListener('touchstart', start, { passive: false });
    surface.addEventListener('touchmove', move, { passive: false });
    surface.addEventListener('touchend', end);
    surface.addEventListener('touchcancel', end);
  }

  push(ev) {
    this.events.push(ev);
  }

  /** 이동 벡터 (길이 ≤ 1) */
  moveVector() {
    if (!this.enabled) return [0, 0];
    let x = 0;
    let y = 0;
    for (const code of this.down) {
      const v = MOVE_KEYS[code];
      if (v) { x += v[0]; y += v[1]; }
    }
    if (x || y) {
      const l = Math.hypot(x, y);
      return [x / l, y / l];
    }
    if (this.joy.active) {
      const l = Math.hypot(this.joy.x, this.joy.y);
      if (l < 0.2) return [0, 0];
      const k = Math.min(1, (l - 0.2) / 0.6) / l;
      return [this.joy.x * k, this.joy.y * k];
    }
    return [0, 0];
  }

  drain() {
    const e = this.events;
    this.events = [];
    return e;
  }

  reset() {
    this.down.clear();
    this.events = [];
    this.joy.active = false;
    this.joy.x = this.joy.y = 0;
    if (this.joyEl) this.joyEl.classList.remove('on');
  }
}

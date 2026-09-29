// 스프라이트 아틀라스 로더. tools/make_sprites.py 가 만든 atlas.json + PNG 시트를 읽는다.
export class Sprites {
  constructor() {
    this.frames = {};
    this.sheets = {};
    this.missing = new Set();
  }

  async load(base = '/static/assets/') {
    const v = (window.__BOOT__ && window.__BOOT__.version) || '';
    const res = await fetch(`${base}atlas.json?v=${v}`);
    const atlas = await res.json();
    this.tile = atlas.tile;
    const jobs = Object.entries(atlas.sheets).map(([name, file]) => new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => { this.sheets[name] = img; resolve(); };
      img.onerror = reject;
      img.src = `${base}${file}?v=${v || atlas.version}`;
    }));
    await Promise.all(jobs);
    this.frames = atlas.frames;
    return this;
  }

  has(name) {
    return name in this.frames;
  }

  /** 이름으로 프레임을 그린다. w/h 생략 시 원본 크기. flip: 좌우 반전 */
  draw(ctx, name, x, y, w, h, flip = false) {
    const f = this.frames[name];
    if (!f) {
      if (!this.missing.has(name)) {
        this.missing.add(name);
        console.warn('[sprites] missing frame', name);
      }
      return;
    }
    const img = this.sheets[f[0]];
    const dw = w == null ? f[3] : w;
    const dh = h == null ? f[4] : h;
    if (flip) {
      ctx.save();
      ctx.translate(x + dw, y);
      ctx.scale(-1, 1);
      ctx.drawImage(img, f[1], f[2], f[3], f[4], 0, 0, dw, dh);
      ctx.restore();
    } else {
      ctx.drawImage(img, f[1], f[2], f[3], f[4], x, y, dw, dh);
    }
  }
}

// Web Audio API 합성 사운드 (외부 파일 없음).
// 효과음 + 물방울/바람 앰비언트 + 열쇠를 모을수록 악기 레이어가 늘어나는 배경음.
import { CONFIG } from './config.js';

// A 단조 계열 (Hz)
const NOTE = (n) => 440 * Math.pow(2, (n - 69) / 12);
const BASS = [45, 45, 41, 43];                 // A2 A2 F2 G2 (마디마다)
const PAD = [[57, 60, 64], [57, 60, 64], [53, 57, 60], [55, 59, 62]];
const ARP = [69, 72, 76, 72, 69, 76, 72, 67];
const MELODY = [76, null, 74, 72, null, 71, 72, null, 74, null, 76, 79, null, 77, 76, null];

export class Audio {
  constructor() {
    this.ctx = null;
    this.sfxVol = CONFIG.audio.defaultSfx;
    this.bgmVol = CONFIG.audio.defaultBgm;
    this.layers = 0;
    this.playing = false;
  }

  /** 첫 사용자 입력 후 호출 */
  unlock() {
    if (this.ctx) {
      if (this.ctx.state === 'suspended') this.ctx.resume();
      return;
    }
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    const ctx = (this.ctx = new AC());
    this.master = ctx.createGain();
    this.master.connect(ctx.destination);
    this.sfx = ctx.createGain();
    this.sfx.gain.value = this.sfxVol;
    this.sfx.connect(this.master);
    this.bgm = ctx.createGain();
    this.bgm.gain.value = this.bgmVol * 0.5;
    this.bgm.connect(this.master);
    // 공용 잔향 (짧은 딜레이 피드백)
    this.verb = ctx.createDelay(1.0);
    this.verb.delayTime.value = 0.23;
    const fb = ctx.createGain();
    fb.gain.value = 0.35;
    const lp = ctx.createBiquadFilter();
    lp.type = 'lowpass';
    lp.frequency.value = 2200;
    this.verb.connect(lp);
    lp.connect(fb);
    fb.connect(this.verb);
    const wet = ctx.createGain();
    wet.gain.value = 0.35;
    lp.connect(wet);
    wet.connect(this.master);
    // 노이즈 버퍼
    const len = ctx.sampleRate * 2;
    this.noise = ctx.createBuffer(1, len, ctx.sampleRate);
    const d = this.noise.getChannelData(0);
    for (let i = 0; i < len; i++) d[i] = Math.random() * 2 - 1;
  }

  setVolumes(sfx, bgm) {
    this.sfxVol = sfx;
    this.bgmVol = bgm;
    if (!this.ctx) return;
    this.sfx.gain.setTargetAtTime(sfx, this.ctx.currentTime, 0.05);
    this.bgm.gain.setTargetAtTime(bgm * 0.5, this.ctx.currentTime, 0.05);
  }

  // ---------- 합성 도구 ----------
  _tone(freq, t0, dur, { type = 'sine', gain = 0.3, attack = 0.005, dest = null, glide = null, verb = 0 } = {}) {
    const ctx = this.ctx;
    const o = ctx.createOscillator();
    const g = ctx.createGain();
    o.type = type;
    o.frequency.setValueAtTime(freq, t0);
    if (glide) o.frequency.exponentialRampToValueAtTime(glide, t0 + dur);
    g.gain.setValueAtTime(0.0001, t0);
    g.gain.exponentialRampToValueAtTime(gain, t0 + attack);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    o.connect(g);
    g.connect(dest || this.sfx);
    if (verb) {
      const s = ctx.createGain();
      s.gain.value = verb;
      g.connect(s);
      s.connect(this.verb);
    }
    o.start(t0);
    o.stop(t0 + dur + 0.05);
  }

  _noise(t0, dur, { freq = 1000, q = 1, type = 'bandpass', gain = 0.3, attack = 0.003, dest = null, sweep = null } = {}) {
    const ctx = this.ctx;
    const src = ctx.createBufferSource();
    src.buffer = this.noise;
    src.loop = true;
    const f = ctx.createBiquadFilter();
    f.type = type;
    f.frequency.setValueAtTime(freq, t0);
    if (sweep) f.frequency.exponentialRampToValueAtTime(sweep, t0 + dur);
    f.Q.value = q;
    const g = ctx.createGain();
    g.gain.setValueAtTime(0.0001, t0);
    g.gain.exponentialRampToValueAtTime(gain, t0 + attack);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    src.connect(f);
    f.connect(g);
    g.connect(dest || this.sfx);
    src.start(t0, Math.random() * 1.5);
    src.stop(t0 + dur + 0.05);
  }

  // ---------- 효과음 ----------
  play(name, opt = {}) {
    if (!this.ctx || this.ctx.state !== 'running') return;
    const t = this.ctx.currentTime;
    switch (name) {
      case 'step': {
        const f = 700 + Math.random() * 300;
        this._noise(t, 0.07, { freq: f, q: 1.2, gain: 0.12 });
        this._tone(90 + Math.random() * 20, t, 0.06, { type: 'triangle', gain: 0.08 });
        break;
      }
      case 'torch_start':
        this._noise(t, 0.35, { freq: 400, sweep: 2500, q: 0.7, gain: 0.18, attack: 0.05 });
        break;
      case 'torch_lit':
        this._noise(t, 0.6, { freq: 1800, sweep: 600, q: 0.5, gain: 0.22, attack: 0.01 });
        for (let i = 0; i < 6; i++) this._noise(t + 0.05 + Math.random() * 0.5, 0.02, { freq: 3000 + Math.random() * 2000, q: 4, gain: 0.12 });
        this._tone(220, t, 0.5, { type: 'triangle', gain: 0.06, glide: 330 });
        break;
      case 'key': {
        const base = [0, 3, 7, 12];
        [76, 83, 88].forEach((n, i) => this._tone(NOTE(n), t + i * 0.08, 0.9, { type: 'sine', gain: 0.18, verb: 0.6 }));
        this._tone(NOTE(95), t + 0.24, 0.6, { type: 'sine', gain: 0.06, verb: 0.8 });
        void base;
        break;
      }
      case 'lock':
        this._noise(t, 0.04, { freq: 3500, q: 6, gain: 0.3 });
        this._tone(1400, t + 0.03, 0.08, { type: 'square', gain: 0.05 });
        this._noise(t + 0.06, 0.05, { freq: 1800, q: 5, gain: 0.2 });
        break;
      case 'door_open':
        this._noise(t, 1.4, { freq: 180, type: 'lowpass', q: 0.8, gain: 0.35, attack: 0.1 });
        this._tone(70, t, 1.2, { type: 'sawtooth', gain: 0.06, glide: 45 });
        this._tone(NOTE(57), t + 0.3, 1.5, { type: 'triangle', gain: 0.08, verb: 0.5 });
        break;
      case 'tp_charge':
        this._tone(220, t, 1.0, { type: 'sine', gain: 0.12, glide: 880, attack: 0.3 });
        this._tone(330, t, 1.0, { type: 'triangle', gain: 0.05, glide: 1320, attack: 0.3 });
        break;
      case 'tp_active':
        [81, 88, 93].forEach((n, i) => this._tone(NOTE(n), t + i * 0.05, 0.7, { type: 'triangle', gain: 0.1, verb: 0.7 }));
        break;
      case 'tp_depart':
        this._noise(t, 0.5, { freq: 300, sweep: 5000, q: 2, gain: 0.2, attack: 0.1 });
        this._tone(440, t, 0.5, { type: 'sine', gain: 0.1, glide: 1760 });
        break;
      case 'tp_arrive':
        this._noise(t, 0.35, { freq: 5000, sweep: 400, q: 2, gain: 0.15 });
        this._tone(1760, t, 0.3, { type: 'sine', gain: 0.08, glide: 440 });
        break;
      case 'denied':
        this._tone(160, t, 0.15, { type: 'square', gain: 0.05 });
        this._tone(120, t + 0.12, 0.2, { type: 'square', gain: 0.05 });
        break;
      case 'ui':
        this._tone(NOTE(84), t, 0.08, { type: 'triangle', gain: 0.06 });
        break;
      case 'clear': {
        const seq = [69, 72, 76, 81, 76, 81, 84, 88];
        seq.forEach((n, i) => this._tone(NOTE(n), t + i * 0.11, 0.5, { type: 'triangle', gain: 0.14, verb: 0.5 }));
        [69, 73, 76, 81].forEach((n) => this._tone(NOTE(n), t + 0.9, 1.8, { type: 'sine', gain: 0.1, attack: 0.05, verb: 0.6 }));
        this._tone(NOTE(45), t + 0.9, 1.8, { type: 'triangle', gain: 0.15 });
        break;
      }
      default:
    }
  }

  // ---------- 배경음 ----------
  startMusic() {
    if (!this.ctx || this.playing) return;
    this.playing = true;
    this.layers = 0;
    this.step = 0;
    this.nextT = this.ctx.currentTime + 0.1;
    this.windGain = this.ctx.createGain();
    this.windGain.gain.value = 0.0001;
    this.windGain.connect(this.bgm);
    // 바람: 느리게 흔들리는 저역 노이즈
    const src = this.ctx.createBufferSource();
    src.buffer = this.noise;
    src.loop = true;
    const f = this.ctx.createBiquadFilter();
    f.type = 'bandpass';
    f.frequency.value = 350;
    f.Q.value = 0.6;
    const lfo = this.ctx.createOscillator();
    lfo.frequency.value = 0.07;
    const lfoG = this.ctx.createGain();
    lfoG.gain.value = 200;
    lfo.connect(lfoG);
    lfoG.connect(f.frequency);
    src.connect(f);
    f.connect(this.windGain);
    src.start();
    lfo.start();
    this.windSrc = src;
    this.windLfo = lfo;
    this.windGain.gain.setTargetAtTime(0.12, this.ctx.currentTime, 1.5);
    this.timer = setInterval(() => this._schedule(), 50);
  }

  stopMusic() {
    if (!this.playing) return;
    this.playing = false;
    clearInterval(this.timer);
    const t = this.ctx.currentTime;
    this.windGain.gain.setTargetAtTime(0.0001, t, 0.3);
    const src = this.windSrc;
    const lfo = this.windLfo;
    setTimeout(() => { try { src.stop(); lfo.stop(); } catch { /* 이미 정지 */ } }, 1500);
  }

  /** 모은 열쇠 비율에 따라 악기 레이어 (0~4) */
  setProgress(collected, total) {
    this.layers = total ? Math.round((collected / total) * 4) : 0;
  }

  _schedule() {
    const ctx = this.ctx;
    if (!ctx || ctx.state !== 'running') return;
    const spb = 60 / CONFIG.audio.bpm / 2; // 8분음표
    while (this.nextT < ctx.currentTime + 0.2) {
      const s = this.step;
      const t = this.nextT;
      const bar = Math.floor(s / 8) % 4;
      // 물방울: 무작위 핑
      if (Math.random() < 0.06) {
        const f = 1200 + Math.random() * 1600;
        this._tone(f, t, 0.18, { type: 'sine', gain: 0.05, glide: f * 0.55, dest: this.bgm, verb: 0.9 });
      }
      // 레이어 1: 베이스 드론
      if (this.layers >= 1 && s % 8 === 0) {
        this._tone(NOTE(BASS[bar]), t, spb * 8, { type: 'triangle', gain: 0.12, attack: 0.3, dest: this.bgm });
      }
      // 레이어 2: 패드
      if (this.layers >= 2 && s % 8 === 0) {
        for (const n of PAD[bar]) this._tone(NOTE(n), t, spb * 8, { type: 'sine', gain: 0.04, attack: 0.8, dest: this.bgm, verb: 0.3 });
      }
      // 레이어 3: 아르페지오
      if (this.layers >= 3) {
        const n = ARP[s % 8] + (bar === 2 ? -4 : bar === 3 ? -2 : 0);
        this._tone(NOTE(n), t, spb * 0.9, { type: 'triangle', gain: 0.035, dest: this.bgm, verb: 0.4 });
      }
      // 레이어 4: 멜로디
      if (this.layers >= 4) {
        const n = MELODY[s % 16];
        if (n) this._tone(NOTE(n), t, spb * 1.8, { type: 'square', gain: 0.025, attack: 0.02, dest: this.bgm, verb: 0.5 });
      }
      this.step++;
      this.nextT += spb;
    }
  }
}

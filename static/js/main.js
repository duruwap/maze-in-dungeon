// 진입점: 화면 전환, 게임 루프, 저장/이어하기, 효과 연결.
import { CONFIG } from './config.js';
import { Game } from './game.js';
import { Renderer, hash2 } from './render.js';
import { Particles } from './particles.js';
import { Minimap } from './minimap.js';
import { Hud } from './hud.js';
import { Input } from './input.js';
import { Audio } from './audio.js';
import { Sprites } from './sprites.js';
import * as api from './api.js';
import { load, save, remove } from './storage.js';
import { t, setLang, detectLang, getLang, formatTime, onLangChange, LANGS } from './i18n.js';
import { shareKakao, webShare, copyLink, kakaoAvailable, initKakao } from './share.js';

const $ = (id) => document.getElementById(id);
const SAVE_MAX_AGE = 24 * 3600 * 1000;

const S = {
  screen: 'title',
  game: null,
  session: null,      // {mode, difficulty, board, token}
  settings: { sfx: CONFIG.audio.defaultSfx, bgm: CONFIG.audio.defaultBgm, shake: true, flicker: true, ...load('settings', {}) },
  lastSave: 0,
  fps: 60,
  result: null,
  clearTimer: null,
  rankingTab: 'daily',
};

const sprites = new Sprites();
const particles = new Particles();
const audio = new Audio();
const input = new Input();
let renderer;
let minimap;
let hud;

// ---------------- 공통 UI ----------------
function flashMsg(text, ms = 2200) {
  const el = $('flash-msg');
  el.textContent = text;
  el.classList.add('on');
  clearTimeout(flashMsg.tid);
  flashMsg.tid = setTimeout(() => el.classList.remove('on'), ms);
}

function loading(on, key = 'title.loading') {
  $('loading-text').textContent = t(key);
  $('loading').hidden = !on;
}

function showScreen(name) {
  S.screen = name;
  for (const id of ['title', 'result', 'ranking']) $(`screen-${id}`).hidden = id !== name;
  const playing = name === null;
  document.body.classList.toggle('playing', playing);
  hud.show(playing);
  input.enabled = playing;
  if (!playing) $('mapview').hidden = true;
  if (name === 'title') refreshTitle();
}

function openModal(id) {
  $(id).hidden = false;
  audio.play('ui');
}

function closeModal(id) {
  $(id).hidden = true;
}

// ---------------- 게임 시작/종료 ----------------
async function startGame(mode, difficulty) {
  loading(true, 'title.generating');
  try {
    await api.ensurePlayer();
    const maze = await api.getMaze(mode, difficulty);
    const session = { mode, difficulty: maze.difficulty, board: maze.board, token: maze.token };
    delete maze.token;
    beginGame(maze, session, null);
  } catch (e) {
    console.warn('[game] start failed', e);
    flashMsg(t('error.network'));
  } finally {
    loading(false);
  }
}

function beginGame(maze, session, state) {
  clearTimeout(S.clearTimer);
  const game = new Game(maze, { resumed: !!state });
  if (state) game.restore(state);
  S.game = game;
  S.session = session;
  S.result = null;
  particles.clear();
  renderer.setGame(game);
  minimap.setGame(game);
  const first = !load('played', false);
  hud.setGame(game, first);
  save('played', true);
  closeModal('modal-pause');
  showScreen(null);
  input.reset();
  audio.unlock();
  audio.startMusic();
  audio.setProgress(game.collectedCount(), game.totalKeys);
  updateMapView();
  S.lastSave = performance.now();
  saveProgress();
}

function saveProgress() {
  const g = S.game;
  if (!g || g.finished) return;
  save('save', { maze: g.maze, session: { ...S.session, token: null }, state: g.serialize(), savedAt: Date.now() });
}

function quitToTitle() {
  clearTimeout(S.clearTimer);
  remove('save');
  S.game = null;
  audio.stopMusic();
  setPaused(false);
  showScreen('title');
}

function setPaused(on) {
  const g = S.game;
  if (g) g.paused = on && !g.finished;
  const paused = !!(g && g.paused);
  $('modal-pause').hidden = !paused;
  document.body.classList.toggle('paused', paused);
  input.reset();
  if (paused) saveProgress();
}

// ---------------- 지도 / 텔레포트 선택 ----------------
function updateMapView() {
  const g = S.game;
  const open = !!g && (g.mode === 'map' || g.mode === 'tpselect');
  const mv = $('mapview');
  if (mv.hidden === !open) return;
  mv.hidden = !open;
  document.body.classList.toggle('mapopen', open);
  document.body.classList.toggle('tpselect', open && g.mode === 'tpselect');
  if (open) {
    const touch = document.body.classList.contains('touch');
    if (g.mode === 'map') {
      $('map-title').textContent = t('map.title');
      $('map-hint').textContent = t(touch ? 'map.close_hint_touch' : 'map.close_hint');
    } else {
      $('map-title').textContent = t('teleport.choose');
      $('map-hint').textContent = t(touch ? 'teleport.choose_hint_touch' : 'teleport.choose_hint');
    }
    const c = $('bigmap');
    const r = c.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 3);
    c.width = Math.max(1, Math.round(r.width * dpr));
    c.height = Math.max(1, Math.round(r.height * dpr));
  }
}

function drawBigMap() {
  const g = S.game;
  const c = $('bigmap');
  const ctx = c.getContext('2d');
  ctx.clearRect(0, 0, c.width, c.height);
  S.bigmapGeom = minimap.draw(ctx, 0, 0, c.width, c.height, { big: true, tpSel: g.mode === 'tpselect' ? g.tpSel : null });
}

function onBigMapTap(e) {
  const g = S.game;
  if (!g) return;
  e.preventDefault();
  if (g.mode === 'tpselect' && S.bigmapGeom) {
    const c = $('bigmap');
    const r = c.getBoundingClientRect();
    const k = c.width / r.width;
    const x = (e.clientX - r.left) * k;
    const y = (e.clientY - r.top) * k;
    const { mx, my, cell } = S.bigmapGeom;
    let best = null;
    let bd = Math.max(22 * k, cell * 2.5);
    for (const i of g.tpSel.options) {
      const tp = g.teleports[i];
      const d = Math.hypot(mx + (tp.x + 0.5) * cell - x, my + (tp.y + 0.5) * cell - y);
      if (d < bd) { bd = d; best = i; }
    }
    if (best != null) {
      g.selectTeleport(best);
      g.confirmTeleport();
      return;
    }
  }
  g.cancelOverlay();
}

// ---------------- 효과 이벤트 ----------------
function processFx(g) {
  const fx = g.fx;
  if (!fx.length) return;
  g.fx = [];
  for (const e of fx) {
    switch (e.type) {
      case 'step':
        audio.play('step');
        particles.burst(e.x, e.y, 'foot', 3, 0.5, 0.35, { up: -0.2 });
        break;
      case 'torch_lit':
        audio.play('torch_start');
        audio.play('torch_lit');
        particles.burst(e.x, e.y - 0.4, 'ember', 18, 1.6, 0.8, { layer: 'over', glow: true, up: -0.8 });
        break;
      case 'key':
        audio.play('key');
        particles.burst(e.x, e.y, e.color, 26, 2.4, 0.9, { layer: 'over', glow: true, size: 1.5 });
        particles.burst(e.x, e.y, 'gold', 10, 1.2, 1.2, { layer: 'over', glow: true, up: -0.5 });
        hud.toast(t('toast.key', { color: t(`color.${e.color}`) }));
        audio.setProgress(e.collected, g.totalKeys);
        break;
      case 'key_inserted':
        hud.toast(t('toast.key_inserted', { left: e.left }));
        break;
      case 'tp_active':
        audio.play('tp_charge');
        audio.play('tp_active');
        particles.burst(e.x, e.y, 'teal', 20, 0.8, 1.0, { layer: 'over', glow: true, up: -0.6 });
        particles.burst(e.x, e.y, 'teal', 24, 1.8, 0.8, { layer: 'over', glow: true });
        break;
      case 'tp_depart':
        audio.play('tp_depart');
        particles.burst(e.x, e.y - 0.3, 'teal', 30, 1.4, 0.6, { layer: 'over', glow: true, up: -1.2 });
        break;
      case 'tp_arrive':
        audio.play('tp_arrive');
        particles.burst(e.x, e.y - 0.3, 'teal', 30, 2.2, 0.5, { layer: 'over', glow: true });
        break;
      case 'lock':
        audio.play('lock');
        break;
      case 'door_open': {
        audio.play('door_open');
        renderer.shake(CONFIG.shake.door, CONFIG.shake.doorMs);
        hud.toast(t('toast.door_open'));
        const d = g.maze.door;
        particles.burst(d.x + 0.5, d.y + 0.8, 'dust', 30, 1.5, 1.0);
        break;
      }
      case 'denied':
        audio.play('denied');
        break;
      case 'ui_open':
        updateMapView();
        audio.play('ui');
        break;
      case 'ui_move':
        audio.play('ui');
        break;
      case 'clear':
        onClear(g);
        break;
      default:
    }
  }
}

function onClear(g) {
  audio.play('clear');
  audio.stopMusic();
  renderer.flash();
  const p = g.player;
  particles.burst(p.x, p.y - 0.5, 'gold', 50, 3, 1.4, { layer: 'over', glow: true, size: 1.5 });
  remove('save');
  S.clearTimer = setTimeout(() => showResult(g), 1900);
}

// ---------------- 결과 ----------------
function countActivated(g) {
  let n = 0;
  g.teleports.forEach((tp, i) => { if (g.tpActive[i] && !tp.active) n++; });
  return n;
}

async function showResult(g) {
  const s = S.session;
  const r = {
    timeMs: Math.round(g.elapsed),
    torches: g.litTorchCount(),
    teleports: countActivated(g),
    explored: g.exploredRatio(),
    mode: s.mode, difficulty: s.difficulty, board: s.board,
    runId: null, rank: null, total: null, topPercent: null, showPercent: false,
  };
  S.result = r;
  showScreen('result');
  $('result-time').textContent = formatTime(r.timeMs);
  $('stat-torches').textContent = t('result.count', { n: r.torches });
  $('stat-teleports').textContent = t('result.count', { n: r.teleports });
  $('stat-explored').textContent = t('result.percent', { percent: Math.round(r.explored * 100) });
  $('result-newbest').hidden = true;
  $('result-rank').textContent = '';
  $('stat-best').textContent = '';
  drawResultPath(g);
  updateShareButtons();

  const localKey = `best.${s.board}`;
  const prevLocal = load(localKey);
  if (prevLocal == null || r.timeMs < prevLocal) save(localKey, r.timeMs);

  if (g.resumed || !s.token) {
    $('result-note').textContent = t('result.resumed_note');
    const best = Math.min(r.timeMs, prevLocal == null ? Infinity : prevLocal);
    $('stat-best').textContent = t('result.best', { time: formatTime(best) });
    return;
  }
  $('result-note').textContent = t('result.saving');
  try {
    const res = await api.submitRun({
      token: s.token,
      time_ms: r.timeMs,
      torches: r.torches,
      teleports: r.teleports,
      explored: Math.round(r.explored * 1000) / 1000,
      path_preview: g.pathPreview(),
      lang: getLang(),
    });
    s.token = null;
    Object.assign(r, {
      runId: res.run_id, rank: res.rank, total: res.total, topPercent: res.top_percent, showPercent: res.show_percent,
    });
    if (S.result !== r) return;
    renderRank(r);
    $('result-note').textContent = '';
    $('result-newbest').hidden = !res.is_new_best;
    $('stat-best').textContent = t('result.best', { time: formatTime(res.best) });
    updateShareButtons();
  } catch (e) {
    console.warn('[result] submit failed', e);
    $('result-note').textContent = t('result.save_failed');
  }
}

function renderRank(r) {
  if (!r.rank) { $('result-rank').textContent = ''; return; }
  $('result-rank').textContent = r.showPercent
    ? `${t('top_percent', { percent: r.topPercent })} · ${t('result.rank', { rank: r.rank })}`
    : t('result.rank_of', { rank: r.rank, total: r.total });
}

function drawResultPath(g) {
  const c = $('result-path');
  const dpr = Math.min(window.devicePixelRatio || 1, 3);
  const size = Math.round(150 * dpr);
  c.width = c.height = size;
  const ctx = c.getContext('2d');
  ctx.imageSmoothingEnabled = false;
  const cell = size / g.W;
  for (let i = 0; i < g.W * g.H; i++) {
    const s = g.seen[i];
    if (!s) continue;
    const wall = g.tiles[i] === 0;
    ctx.fillStyle = wall ? '#2a3150' : s === 2 ? '#ffb347' : '#3b3f5c';
    ctx.fillRect((i % g.W) * cell, ((i / g.W) | 0) * cell, Math.ceil(cell), Math.ceil(cell));
  }
  const e = g.maze.exit;
  ctx.fillStyle = '#48e0d0';
  ctx.fillRect((e.x - 0.5) * cell, (e.y - 0.5) * cell, cell * 2, cell * 2);
}

function updateShareButtons() {
  const r = S.result;
  const ko = getLang() === 'ko';
  const kakao = $('btn-kakao');
  kakao.hidden = !kakaoAvailable() || !r || !r.runId;
  $('btn-webshare').hidden = !navigator.share;
  const row = $('share-row');
  // 한국어일 때 카카오톡 버튼을 가장 앞에
  if (ko) row.prepend(kakao); else row.append(kakao);
}

// ---------------- 랭킹 ----------------
async function openRanking(tab) {
  S.rankingTab = tab || S.rankingTab;
  showScreen('ranking');
  document.querySelectorAll('#screen-ranking .tab').forEach((b) => b.classList.toggle('on', b.dataset.board === S.rankingTab));
  const list = $('ranking-list');
  const me = $('ranking-me');
  list.innerHTML = `<li class="ranking-empty">${t('ranking.loading')}</li>`;
  me.innerHTML = '';
  $('ranking-sub').innerHTML = '';
  const tab0 = S.rankingTab;
  try {
    await api.ensurePlayer();
    const data = await api.leaderboard(tab0);
    if (S.rankingTab !== tab0 || S.screen !== 'ranking') return;
    const sub = $('ranking-sub');
    const a = document.createElement('span');
    a.textContent = t(tab0 === 'daily' ? 'ranking.reset_daily' : 'ranking.reset_weekly');
    const b = document.createElement('span');
    b.textContent = t('ranking.players', { n: data.total });
    sub.append(a, b);
    list.innerHTML = '';
    if (!data.entries.length) {
      list.innerHTML = `<li class="ranking-empty"></li>`;
      list.firstChild.textContent = t('ranking.empty');
    }
    for (const e of data.entries) list.appendChild(rankRow(e, e.is_me));
    if (data.me && !data.me.in_top) {
      const row = rankRow({ rank: data.me.rank, number: data.me.number, time_ms: data.me.time_ms }, true, 'div');
      row.className = 'me-row';
      me.appendChild(row);
    }
    const mine = list.querySelector('li.me');
    if (mine) mine.scrollIntoView({ block: 'center' });
  } catch (e) {
    console.warn('[ranking] load failed', e);
    list.innerHTML = `<li class="ranking-empty"></li>`;
    list.firstChild.textContent = t('ranking.error');
  }
}

function rankRow(e, isMe, tag = 'li') {
  const li = document.createElement(tag);
  if (isMe) li.classList.add('me');
  const rk = document.createElement('span');
  rk.className = 'rk';
  rk.textContent = `#${e.rank}`;
  const nm = document.createElement('span');
  nm.textContent = t('explorer_name', { n: e.number }) + (isMe ? ` (${t('ranking.me')})` : '');
  const tm = document.createElement('span');
  tm.className = 'tm';
  tm.textContent = formatTime(e.time_ms);
  li.append(rk, nm, tm);
  return li;
}

// ---------------- 타이틀 ----------------
async function refreshTitle() {
  const p = api.getPlayer();
  $('explorer-name').textContent = p ? t('explorer_name', { n: p.number }) : '';
  const localBest = load(`best.daily:${todayKst()}`);
  $('today-best').textContent = localBest != null ? t('title.today_best', { time: formatTime(localBest) }) : t('title.no_record');
  if (!p) return;
  try {
    const data = await api.leaderboard('daily');
    if (data.me && data.me.time_ms != null) {
      $('today-best').textContent = t('title.today_best', { time: formatTime(data.me.time_ms) });
    }
  } catch { /* 오프라인이면 로컬 기록 유지 */ }
}

function todayKst() {
  const d = new Date(Date.now() + 9 * 3600 * 1000);
  return d.toISOString().slice(0, 10);
}

let titleTiles = null;
function drawTitleBg(time) {
  const c = $('title-bg');
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const w = Math.round(c.clientWidth * dpr);
  const h = Math.round(c.clientHeight * dpr);
  if (!w || !h) return;
  if (c.width !== w || c.height !== h) { c.width = w; c.height = h; titleTiles = null; }
  const ctx = c.getContext('2d');
  ctx.imageSmoothingEnabled = false;
  const scale = Math.max(2, Math.round(Math.min(w, h) / 220));
  const tp = 16 * scale;
  const cols = Math.ceil(w / tp) + 1;
  const rows = Math.ceil(h / tp) + 1;
  if (!titleTiles) {
    // 벽으로 둘러싸인 방 + 벽 횃불 몇 개
    const off = document.createElement('canvas');
    off.width = cols * tp;
    off.height = rows * tp;
    const o = off.getContext('2d');
    o.imageSmoothingEnabled = false;
    const wallRow = 2;
    for (let y = 0; y < rows; y++) {
      for (let x = 0; x < cols; x++) {
        const hv = hash2(x, y, 99);
        if (y < wallRow) sprites.draw(o, 'wall.top.15', x * tp, y * tp, tp, tp);
        else if (y === wallRow) sprites.draw(o, `wall.face.${hv % 7 === 0 ? 2 : hv % 5 === 0 ? 1 : 0}`, x * tp, y * tp, tp, tp);
        else {
          sprites.draw(o, `floor.corr.${hv % 4}`, x * tp, y * tp, tp, tp);
          if (y === wallRow + 1) sprites.draw(o, 'shade.n', x * tp, y * tp, tp, tp);
          if (hv % 17 === 0) sprites.draw(o, `decor.${['pebbles', 'bones', 'puddle', 'rune'][hv % 4]}.${hv % 2}`, x * tp, y * tp, tp, tp);
        }
      }
    }
    titleTiles = { canvas: off, torches: [], wallRow };
    for (let x = 1; x < cols; x += 5) titleTiles.torches.push(x);
  }
  ctx.drawImage(titleTiles.canvas, 0, 0);
  const f = Math.floor(time * 8);
  for (const x of titleTiles.torches) sprites.draw(ctx, `torch.on.${(f + x) % 4}`, x * tp, titleTiles.wallRow * tp, tp, tp);
  // 어둠 + 횃불빛
  ctx.globalCompositeOperation = 'source-over';
  ctx.fillStyle = 'rgba(11,14,26,0.55)';
  ctx.fillRect(0, 0, w, h);
  ctx.globalCompositeOperation = 'lighter';
  for (const x of titleTiles.torches) {
    const cx = (x + 0.5) * tp;
    const cy = (titleTiles.wallRow + 0.6) * tp;
    const r = tp * 4.2 * (S.settings.flicker ? 1 + 0.03 * Math.sin(time * 9 + x) : 1);
    const gr = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
    gr.addColorStop(0, 'rgba(255,179,71,0.35)');
    gr.addColorStop(1, 'rgba(255,179,71,0)');
    ctx.fillStyle = gr;
    ctx.fillRect(cx - r, cy - r, r * 2, r * 2);
  }
  ctx.globalCompositeOperation = 'source-over';
  const vg = ctx.createLinearGradient(0, h * 0.35, 0, h);
  vg.addColorStop(0, 'rgba(11,14,26,0)');
  vg.addColorStop(1, 'rgba(11,14,26,0.95)');
  ctx.fillStyle = vg;
  ctx.fillRect(0, 0, w, h);
}

// ---------------- 방법 그림 ----------------
function drawHowto() {
  document.querySelectorAll('.howto-pic').forEach((c) => {
    const step = +c.dataset.step;
    c.width = 160;
    c.height = 120;
    const ctx = c.getContext('2d');
    ctx.imageSmoothingEnabled = false;
    ctx.fillStyle = '#0b0e1a';
    ctx.fillRect(0, 0, 160, 120);
    const T = 32;
    const map = [
      '#####',
      '#...#',
      '#...#',
      '#...#',
    ];
    const drawRoom = () => {
      for (let y = 0; y < 4; y++) {
        for (let x = 0; x < 5; x++) {
          const ch = map[y][x];
          if (ch === '#') {
            const face = y === 0 && x > 0 && x < 4;
            sprites.draw(ctx, face ? `wall.face.${x % 3 === 0 ? 1 : 0}` : 'wall.top.15', x * T, y * T - 8, T, T);
          } else {
            sprites.draw(ctx, `floor.corr.${(x + y) % 4}`, x * T, y * T - 8, T, T);
            if (y === 1) sprites.draw(ctx, 'shade.n', x * T, y * T - 8, T, T);
          }
        }
      }
    };
    drawRoom();
    const dark = (cx, cy, r) => {
      const g = ctx.createRadialGradient(cx, cy, r * 0.3, cx, cy, r);
      g.addColorStop(0, 'rgba(11,14,26,0)');
      g.addColorStop(1, 'rgba(11,14,26,0.96)');
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, 160, 120);
    };
    if (step === 1) {
      sprites.draw(ctx, 'player.idle.down.0', 64, 56, T, T);
      dark(80, 74, 46);
    } else if (step === 2) {
      sprites.draw(ctx, 'torch.on.1', 32, -8, T, T);
      sprites.draw(ctx, 'tp.on.2', 96, 56, T, T);
      sprites.draw(ctx, 'player.interact.up.2', 34, 36, T, T);
      dark(60, 40, 110);
    } else {
      sprites.draw(ctx, 'door.3.2', 64, -8, T, T);
      sprites.draw(ctx, 'key.red.0', 20, 60, T, T);
      sprites.draw(ctx, 'key.blue.1', 112, 64, T, T);
      sprites.draw(ctx, 'player.idle.up.0', 64, 30, T, T);
      dark(80, 50, 120);
    }
  });
}

// ---------------- 설정 ----------------
function applySettings() {
  const st = S.settings;
  audio.setVolumes(st.sfx, st.bgm);
  renderer.settings.shake = st.shake;
  renderer.settings.flicker = st.flicker;
  save('settings', st);
}

function bindSettings() {
  const st = S.settings;
  $('set-sfx').value = Math.round(st.sfx * 100);
  $('set-bgm').value = Math.round(st.bgm * 100);
  $('set-shake').checked = st.shake;
  $('set-flicker').checked = st.flicker;
  $('set-sfx').addEventListener('input', (e) => { st.sfx = e.target.value / 100; applySettings(); });
  $('set-sfx').addEventListener('change', () => audio.play('key'));
  $('set-bgm').addEventListener('input', (e) => { st.bgm = e.target.value / 100; applySettings(); });
  $('set-shake').addEventListener('change', (e) => { st.shake = e.target.checked; applySettings(); });
  $('set-flicker').addEventListener('change', (e) => { st.flicker = e.target.checked; applySettings(); });
}

// ---------------- 이벤트 바인딩 ----------------
function bindUi() {
  const click = (id, fn) => $(id).addEventListener('click', (e) => { audio.unlock(); fn(e); });
  click('btn-daily', () => startGame('daily', 'normal'));
  document.querySelectorAll('.btn.diff').forEach((b) => b.addEventListener('click', () => { audio.unlock(); startGame('free', b.dataset.diff); }));
  click('btn-ranking', () => openRanking('daily'));
  click('btn-ranking-back', () => showScreen(S.result ? 'result' : 'title'));
  document.querySelectorAll('#screen-ranking .tab').forEach((b) => b.addEventListener('click', () => openRanking(b.dataset.board)));

  click('btn-settings', () => openModal('modal-settings'));
  click('btn-howto', () => { drawHowto(); openModal('modal-howto'); });
  click('btn-lang', () => {
    document.querySelectorAll('.btn.lang').forEach((b) => b.classList.toggle('on', b.dataset.lang === getLang()));
    openModal('modal-lang');
  });
  document.querySelectorAll('.btn.lang').forEach((b) => b.addEventListener('click', async () => {
    await setLang(b.dataset.lang, true);
    closeModal('modal-lang');
  }));
  document.querySelectorAll('[data-close]').forEach((b) => b.addEventListener('click', () => closeModal(b.closest('.overlay').id)));
  document.querySelectorAll('.overlay:not(.opaque)').forEach((o) => o.addEventListener('click', (e) => {
    if (e.target === o && o.id !== 'modal-resume') closeModal(o.id);
  }));

  const fsBtn = $('btn-fullscreen');
  const fsEl = document.documentElement;
  if (!(fsEl.requestFullscreen || fsEl.webkitRequestFullscreen)) fsBtn.hidden = true;
  fsBtn.addEventListener('click', () => {
    if (document.fullscreenElement || document.webkitFullscreenElement) {
      (document.exitFullscreen || document.webkitExitFullscreen).call(document);
    } else {
      (fsEl.requestFullscreen || fsEl.webkitRequestFullscreen).call(fsEl).catch?.(() => {});
    }
  });

  // 게임 중
  click('btn-pause', () => setPaused(true));
  click('btn-resume', () => setPaused(false));
  click('btn-newmap', () => {
    const s = S.session;
    setPaused(false);
    remove('save');
    startGame(s.mode, s.difficulty);
  });
  click('btn-totitle', quitToTitle);
  $('btn-e').addEventListener('touchstart', (e) => { e.preventDefault(); audio.unlock(); input.push({ type: 'interact' }); }, { passive: false });
  $('btn-e').addEventListener('click', () => input.push({ type: 'interact' }));
  $('minimap').addEventListener('click', () => { if (S.game && S.game.mode === 'play') { S.game.toggleMap(); updateMapView(); } });
  $('bigmap').addEventListener('click', onBigMapTap);
  $('btn-map-close').addEventListener('click', (e) => { e.stopPropagation(); if (S.game) { S.game.cancelOverlay(); updateMapView(); } });
  $('mapview').addEventListener('click', (e) => { if (e.target.id === 'mapview' && S.game) { S.game.cancelOverlay(); updateMapView(); } });

  // 결과
  click('btn-retry', () => startGame(S.session.mode, S.session.difficulty));
  click('btn-result-ranking', () => openRanking(S.session.mode === 'daily' ? 'daily' : S.session.difficulty));
  click('btn-result-title', () => { S.result = null; S.game = null; showScreen('title'); });
  click('btn-kakao', () => { if (!shareKakao(S.result)) flashMsg(t('error.generic')); });
  click('btn-webshare', () => webShare(S.result));
  click('btn-copy', async () => flashMsg((await copyLink(S.result)) ? t('result.copied') : t('error.generic')));

  // 이어하기
  click('btn-resume-yes', () => {
    const sv = load('save');
    closeModal('modal-resume');
    if (sv) beginGame(sv.maze, sv.session, sv.state);
  });
  click('btn-resume-no', () => { remove('save'); closeModal('modal-resume'); });

  // 탭 전환 시 자동 일시정지
  document.addEventListener('visibilitychange', () => {
    if (document.hidden && S.game && S.screen === null && !S.game.finished) setPaused(true);
  });
  window.addEventListener('resize', () => {
    renderer.resize();
    if (hud) hud.resizeMinimap();
    if (S.game && !$('mapview').hidden) { $('mapview').hidden = true; updateMapView(); }
  });
  // 더블탭 확대·핀치 방지
  document.addEventListener('dblclick', (e) => e.preventDefault(), { passive: false });
  document.addEventListener('gesturestart', (e) => e.preventDefault());
  window.addEventListener('pointerdown', () => audio.unlock(), { once: true });
  onLangChange(() => {
    if (S.screen === 'title') refreshTitle();
    if (S.screen === 'result' && S.result) { renderRank(S.result); updateShareButtons(); }
    if (S.screen === 'ranking') openRanking(S.rankingTab);
    if (S.game && hud) hud.refreshHint();
    if (!$('modal-howto').hidden) drawHowto();
  });
}

function handleGameEvent(ev) {
  const g = S.game;
  if (!g || g.paused) return;
  switch (ev.type) {
    case 'escape':
      if (g.cancelOverlay()) break;
      if (!g.finished) setPaused(true);
      break;
    case 'map':
      if (g.mode === 'play' || g.mode === 'map') g.toggleMap();
      break;
    case 'interact':
      g.interact();
      break;
    case 'confirm':
      if (g.mode === 'tpselect') g.confirmTeleport();
      break;
    case 'dir':
      if (g.mode === 'tpselect') g.moveTeleportSelection(ev.dir);
      break;
    default:
  }
  updateMapView();
}

// 텔레포트 선택 중: 조이스틱을 한 방향으로 밀면 그 방향의 텔레포트로 선택이 옮겨간다 (E 버튼으로 이동)
let joyLatched = false;
function joystickSelect(g) {
  const j = input.joy;
  if (g.mode !== 'tpselect' || !j.active) { joyLatched = false; return; }
  const mag = Math.hypot(j.x, j.y);
  if (joyLatched) {
    if (mag < 0.3) joyLatched = false;
    return;
  }
  if (mag < CONFIG.interact.joyFlick) return;
  joyLatched = true;
  const dir = Math.abs(j.x) > Math.abs(j.y) ? (j.x > 0 ? 'right' : 'left') : (j.y > 0 ? 'down' : 'up');
  g.moveTeleportSelection(dir);
}

// ---------------- 메인 루프 ----------------
let last = performance.now();
function frame(now) {
  const dt = Math.min(0.05, Math.max(0, (now - last) / 1000));
  last = now;
  if (dt > 0) S.fps += (1 / dt - S.fps) * 0.05;
  const time = now / 1000;
  const g = S.game;
  if (g && S.screen === null) {
    for (const ev of input.drain()) handleGameEvent(ev);
    joystickSelect(g);
    if (!input.enabled) input.drain();
    g.update(dt, input.moveVector());
    processFx(g);
    particles.update(dt, g, S.fps);
    minimap.update();
    renderer.render(dt, time);
    hud.update(g, now);
    updateMapView();
    if (!$('mapview').hidden) {
      drawBigMap();
      $('map-timer').textContent = formatTime(g.elapsed);
    }
    if (now - S.lastSave > CONFIG.saveIntervalMs && g.started && !g.finished && !g.paused) {
      S.lastSave = now;
      saveProgress();
    }
  } else {
    input.drain();
    if (S.screen === 'title') drawTitleBg(time);
  }
  requestAnimationFrame(frame);
}

async function boot() {
  if (window.matchMedia && window.matchMedia('(pointer: coarse)').matches) {
    document.body.classList.add('touch');
    input.touchMode = true;
  }
  input.bindTouch($('touch-surface'), $('joystick'), $('joystick').querySelector('.knob'));
  input.onFirstInput = () => audio.unlock();
  input.onTouchMode = () => { if (S.game) hud.refreshHint(); };
  const lang = detectLang();
  await setLang(lang, new URLSearchParams(location.search).has('lang'));
  await sprites.load();
  renderer = new Renderer($('game'), sprites, particles);
  minimap = new Minimap(sprites);
  hud = new Hud(sprites, minimap);
  applySettings();
  bindSettings();
  bindUi();
  if (document.readyState === 'complete') initKakao(); else window.addEventListener('load', initKakao);
  showScreen('title');
  api.ensurePlayer().then(refreshTitle).catch((e) => console.warn('[player]', e));
  const sv = load('save');
  if (sv && sv.maze && sv.state && Date.now() - sv.savedAt < SAVE_MAX_AGE) openModal('modal-resume');
  else if (sv) remove('save');
  if (new URLSearchParams(location.search).has('debug')) {
    window.__mid = { S, input, startGame, sprites, renderer: () => renderer, LANGS };
  }
  requestAnimationFrame(frame);
}

boot().catch((e) => {
  console.warn('[boot] failed', e);
  flashMsg('Error: failed to start');
});

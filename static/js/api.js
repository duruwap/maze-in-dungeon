// 서버 API 클라이언트. 모든 요청에 X-Player-Id 헤더를 붙인다.
import { load, save } from './storage.js';

let player = load('player');

export function getPlayer() {
  return player;
}

async function request(method, url, body, retry = true) {
  const headers = { 'Content-Type': 'application/json' };
  if (player) headers['X-Player-Id'] = player.id;
  const res = await fetch(url, { method, headers, body: body ? JSON.stringify(body) : undefined });
  let data = null;
  try { data = await res.json(); } catch { /* 빈 응답 */ }
  if (res.status === 401 && data && data.error === 'unknown_player' && retry) {
    // DB 초기화 등으로 ID가 사라졌으면 다시 발급
    player = null;
    await ensurePlayer();
    return request(method, url, body, false);
  }
  if (!res.ok) {
    const err = new Error((data && data.error) || `http_${res.status}`);
    err.status = res.status;
    err.code = data && data.error;
    throw err;
  }
  return data;
}

export async function ensurePlayer() {
  if (player && player.id) return player;
  const res = await fetch('/api/player', { method: 'POST' });
  if (!res.ok) throw new Error('player_failed');
  player = await res.json();
  save('player', player);
  return player;
}

/** round: 1(쉬움) 2(보통) 3(어려움). 2·3라운드는 1라운드에서 받은 판 토큰을 넘긴다 */
export function getMaze(round, token) {
  const q = new URLSearchParams({ round: String(round) });
  if (token) q.set('token', token);
  return request('GET', `/api/maze?${q}`);
}

export function submitRun(payload) {
  return request('POST', '/api/runs', payload);
}

export function leaderboard(board) {
  const q = new URLSearchParams({ board });
  if (player) q.set('player_id', player.id);
  return request('GET', `/api/leaderboard?${q}`);
}

export function myRuns() {
  return request('GET', `/api/players/${player.id}/runs`);
}

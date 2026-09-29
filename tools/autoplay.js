// 개발용 자동 플레이 봇 (?debug=1 에서 window.__mid 사용).
// BFS로 열쇠 → 문 → 출구 순서로 이동하며 실제 키 입력 상태를 흉내 낸다.
window.__autoplay = function (opts = {}) {
  const M = window.__mid;
  const g = M.S.game;
  const W = g.W;
  const walk = (i) => { const t = g.tiles[i]; return t === 1 || t === 2 || t === 3 || (t === 4 && g.doorOpen); };
  function bfs(from, goal) {
    const prev = new Int32Array(g.W * g.H).fill(-1);
    prev[from] = from;
    const q = [from];
    while (q.length) {
      const i = q.shift();
      if (i === goal) break;
      for (const j of [i - 1, i + 1, i - W, i + W]) {
        if (prev[j] === -1 && walk(j)) { prev[j] = i; q.push(j); }
      }
    }
    if (prev[goal] === -1) return null;
    const path = [];
    for (let i = goal; i !== from; i = prev[i]) path.push(i);
    return path.reverse();
  }
  // 열쇠는 한 번에 하나만: 열쇠 → 문 → 다음 열쇠 ...
  const goals = [];
  const d = g.maze.door;
  g.keys.forEach((k, ki) => {
    goals.push({ type: 'key', k: ki, i: k.y * W + k.x });
    goals.push({ type: 'door', k: ki, i: (d.y + 1) * W + d.x });
  });
  goals.push({ type: 'exit', i: g.maze.exit.y * W + g.maze.exit.x });
  let gi = 0;
  let path = null;
  const input = M.input;
  const press = (codes) => { input.down.clear(); codes.forEach((c) => input.down.add(c)); };
  const state = { done: false, log: [] };
  const timer = setInterval(() => {
    const game = M.S.game;
    if (!game || game.finished) { press([]); state.done = true; clearInterval(timer); return; }
    if (game.action) { press([]); return; }
    if (opts.torches && game.target && game.target.type === 'torch') { press([]); input.push({ type: 'interact' }); return; }
    if (opts.teleports && game.target && game.target.type === 'tpActivate') { press([]); input.push({ type: 'interact' }); return; }
    const p = game.player;
    const cur = Math.floor(p.y) * W + Math.floor(p.x);
    const goal = goals[gi];
    if (!goal) return;
    if (goal.type === 'key' && game.keyState[goal.k] !== 0) { gi++; path = null; return; }
    if (goal.type === 'door' && game.keyState[goal.k] === 2) { gi++; path = null; return; }
    if (cur === goal.i && goal.type !== 'exit') {
      const cx = (goal.i % W) + 0.5; const cy = ((goal.i / W) | 0) + 0.5;
      if (Math.hypot(p.x - cx, p.y - cy) < 0.3 || goal.type === 'key') {
        press([]);
        if (goal.type === 'door') { input.down.add('KeyW'); setTimeout(() => { input.down.clear(); input.push({ type: 'interact' }); }, 60); }
        else input.push({ type: 'interact' });
        return;
      }
    }
    if (!path || path[0] === undefined || (path.indexOf(cur) === -1 && cur !== path.from)) {
      path = bfs(cur, goal.i) || [];
      path.from = cur;
    }
    const idx = path.indexOf(cur);
    const next = idx === -1 ? path[0] : path[idx + 1];
    const tgt = next === undefined ? goal.i : next;
    const tx = (tgt % W) + 0.5; const ty = ((tgt / W) | 0) + 0.5;
    const dx = tx - p.x; const dy = ty - p.y;
    const codes = [];
    if (dx > 0.08) codes.push('KeyD'); else if (dx < -0.08) codes.push('KeyA');
    if (dy > 0.08) codes.push('KeyS'); else if (dy < -0.08) codes.push('KeyW');
    press(codes);
  }, 16);
  return state;
};

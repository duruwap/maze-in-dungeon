// 격자 기반 시야 계산: Recursive Shadowcasting (8 옥탄트).
// 가려진 칸은 절대 표시되지 않는다. 벽 칸 자체는 보인다.

const MULT = [
  [1, 0, 0, -1, -1, 0, 0, 1],
  [0, 1, -1, 0, 0, -1, 1, 0],
  [0, 1, 1, 0, 0, -1, -1, 0],
  [1, 0, 0, 1, -1, 0, 0, -1],
];

/**
 * @param {(x:number,y:number)=>boolean} opaque
 * @param {number} ox 원점 x (칸)
 * @param {number} oy 원점 y (칸)
 * @param {number} radius
 * @param {(x:number,y:number,d2:number)=>void} visit
 */
export function shadowcast(opaque, ox, oy, radius, visit) {
  visit(ox, oy, 0);
  const r2 = radius * radius;
  for (let oct = 0; oct < 8; oct++) {
    cast(opaque, ox, oy, 1, 1.0, 0.0, radius, r2,
      MULT[0][oct], MULT[1][oct], MULT[2][oct], MULT[3][oct], visit);
  }
}

function cast(opaque, cx, cy, row, start, end, radius, r2, xx, xy, yx, yy, visit) {
  if (start < end) return;
  let newStart = 0;
  for (let j = row; j <= radius; j++) {
    let dx = -j - 1;
    const dy = -j;
    let blocked = false;
    while (dx <= 0) {
      dx += 1;
      const X = cx + dx * xx + dy * xy;
      const Y = cy + dx * yx + dy * yy;
      const lSlope = (dx - 0.5) / (dy + 0.5);
      const rSlope = (dx + 0.5) / (dy - 0.5);
      if (start < rSlope) continue;
      if (end > lSlope) break;
      const d2 = dx * dx + dy * dy;
      if (d2 <= r2) visit(X, Y, d2);
      if (blocked) {
        if (opaque(X, Y)) {
          newStart = rSlope;
          continue;
        }
        blocked = false;
        start = newStart;
      } else if (opaque(X, Y) && j < radius) {
        blocked = true;
        cast(opaque, cx, cy, j + 1, start, lSlope, radius, r2, xx, xy, yx, yy, visit);
        newStart = rSlope;
      }
    }
    if (blocked) break;
  }
}

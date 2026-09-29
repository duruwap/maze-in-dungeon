// 모든 게임 수치는 여기서 조정한다.
// (서버 app/maze/validate.py 의 MOVE_SPEED / INTERACT_REACH / DOOR_UNLOCK_MS 와 맞춰야 한다)
export const CONFIG = {
  moveSpeed: 4.5,            // 칸/초
  hitbox: 0.6,               // 플레이어 충돌 박스 (칸)
  cornerAssist: 0.45,        // 벽 모서리에 이만큼 이하로 걸리면 미끄러지듯 보정
  maxStep: 0.25,             // 한 번에 이동하는 최대 거리 (터널링 방지)

  vision: {
    base: 2.0,               // 초기 시야 반경
    adaptEvery: 30,          // 초마다
    adaptStep: 0.5,          // 이만큼 증가
    adaptMax: 3.5,           // 어둠 적응 최대
    perTorch: 0.25,          // 켜진 횃불 1개당
    torchBonusMax: 1.5,
    losRadius: 15,           // 멀리 있는 횃불빛을 볼 수 있는 시선 거리
    lerp: 2.0,               // 반경 변화 부드럽게 (초당)
  },
  torch: { radius: 4, lightMs: 300, flicker: 0.03 },   // lightMs: 켜는 모션(이동을 막지 않음)
  teleport: { activateMs: 600, arriveMs: 300 },  // 연출 시간 (상호작용 효과는 즉시 적용)
  door: { openMs: 500 },
  interact: { reach: 1.2, facingBias: 0.35, standOn: 0.62, keyAnimMs: 250, joyFlick: 0.6 },
  keySparkleRadius: 6,

  saveIntervalMs: 5000,
  statusMs: 1500,
  toastMs: 2200,
  hintMs: 10000,

  // 화면
  tile: 16,
  targetTilesShort: 11,      // 화면 짧은 변에 보일 칸 수 (정수 배율 선택 기준)
  minScale: 2,
  maxScale: 8,
  lightResolution: 0.5,      // 어둠 레이어 해상도 배율

  anim: {
    idleFps: 4,
    walkFpsMin: 10,
    walkFpsMax: 12,
    interactFps: 12,
    teleportFps: 12,
    clearFps: 8,
    torchFps: 8,
    keyFps: 6,
    tpFps: 10,
    doorOpenFps: 8,
  },

  particles: {
    max: 420,
    lowFps: 45,              // 이 FPS 미만이 지속되면 파티클 감소
    lowFpsSeconds: 3,
  },

  shake: { door: 0.18, doorMs: 450 },
  clearFlashMs: 1600,

  palette: {
    dark: [11, 14, 26],        // #0B0E1A
    darkWarm: [26, 19, 16],
    torch: '#FFB347',
    lamp: '#FFE08A',
    teal: '#48E0D0',
    keys: { red: '#E0413A', blue: '#3F7FE0', green: '#4CC25A', yellow: '#F2D03B' },
    mapWall: '#39415e',
    mapSeen: '#1f2438',
    mapVisited: '#6a7396',
    mapExit: '#8e6fd8',
  },

  audio: {
    defaultSfx: 0.8,
    defaultBgm: 0.5,
    bpm: 76,
  },
};

export const DIFF_KEYS = { easy: 2, normal: 3, hard: 4 };
export const KEY_COLORS = ['red', 'blue', 'green', 'yellow'];

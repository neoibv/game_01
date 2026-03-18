// Stage 1: Seoul — Z-based obstacle layout for pseudo-3D
// totalDistance: 4000 Z-units
// Sections:
//   0~800:     Tutorial (barrier, trashcan only)
//   800~2400:  Main game (car, sinkhole added)
//   2400~3600: Advanced (tighter spacing)
//   3600~4000: Climax (max speed, complex combos)

export const STAGE1_DATA = {
  id: 1,
  name: 'STAGE 1 — SEOUL',
  totalDistance: 4000,
  timeLimit: 120,
  checkpointZ: 2000,

  obstacles: [
    // === TUTORIAL (0~800): barrier & trashcan ===
    { type: 'barrier',  z: 180,  x: 0.3 },
    { type: 'trashcan', z: 280,  x: -0.2 },
    { type: 'barrier',  z: 380,  x: -0.4 },
    { type: 'trashcan', z: 470,  x: 0.5 },
    { type: 'barrier',  z: 560,  x: 0.0 },
    { type: 'trashcan', z: 640,  x: -0.6 },
    { type: 'barrier',  z: 720,  x: 0.4 },
    { type: 'trashcan', z: 780,  x: 0.1 },

    // === MAIN GAME (800~2400): cars & sinkholes ===
    { type: 'sinkhole', z: 860,  x: 0.0, width: 0.5 },
    { type: 'car',      z: 960,  x: -0.4, speed: 0.015 },
    { type: 'barrier',  z: 1050, x: 0.5 },
    { type: 'sinkhole', z: 1150, x: 0.2, width: 0.4 },
    { type: 'trashcan', z: 1250, x: -0.3 },
    { type: 'car',      z: 1360, x: 0.3, speed: -0.02 },
    { type: 'sinkhole', z: 1460, x: -0.1, width: 0.45 },
    { type: 'barrier',  z: 1550, x: 0.6 },
    { type: 'car',      z: 1660, x: -0.5, speed: 0.025 },
    { type: 'trashcan', z: 1750, x: 0.2 },
    { type: 'sinkhole', z: 1850, x: 0.0, width: 0.55 },
    { type: 'barrier',  z: 1940, x: -0.4 },
    // checkpoint at 2000
    { type: 'car',      z: 2060, x: 0.3, speed: -0.02 },
    { type: 'trashcan', z: 2140, x: -0.2 },
    { type: 'sinkhole', z: 2230, x: 0.1, width: 0.5 },
    { type: 'barrier',  z: 2320, x: -0.5 },
    { type: 'car',      z: 2400, x: 0.4, speed: 0.03 },

    // === ADVANCED (2400~3600): tighter spacing ===
    { type: 'sinkhole', z: 2480, x: 0.0, width: 0.5 },
    { type: 'barrier',  z: 2540, x: 0.5 },
    { type: 'car',      z: 2610, x: -0.3, speed: -0.03 },
    { type: 'sinkhole', z: 2680, x: 0.2, width: 0.4 },
    { type: 'trashcan', z: 2740, x: -0.5 },
    { type: 'barrier',  z: 2800, x: 0.3 },
    { type: 'car',      z: 2870, x: 0.0, speed: 0.025 },
    { type: 'sinkhole', z: 2940, x: -0.2, width: 0.55 },
    { type: 'trashcan', z: 3000, x: 0.6 },
    { type: 'barrier',  z: 3060, x: -0.4 },
    { type: 'car',      z: 3130, x: 0.2, speed: -0.035 },
    { type: 'sinkhole', z: 3200, x: 0.0, width: 0.6 },
    { type: 'trashcan', z: 3260, x: -0.6 },
    { type: 'barrier',  z: 3320, x: 0.4 },
    { type: 'car',      z: 3390, x: -0.2, speed: 0.04 },
    { type: 'sinkhole', z: 3460, x: 0.1, width: 0.5 },
    { type: 'trashcan', z: 3520, x: 0.5 },
    { type: 'barrier',  z: 3580, x: -0.3 },

    // === CLIMAX (3600~4000): maximum intensity ===
    { type: 'car',      z: 3630, x: 0.3, speed: -0.04 },
    { type: 'sinkhole', z: 3680, x: -0.1, width: 0.55 },
    { type: 'trashcan', z: 3720, x: 0.5 },
    { type: 'barrier',  z: 3760, x: -0.5 },
    { type: 'car',      z: 3800, x: 0.0, speed: 0.045 },
    { type: 'sinkhole', z: 3840, x: 0.2, width: 0.6 },
    { type: 'trashcan', z: 3875, x: -0.4 },
    { type: 'barrier',  z: 3910, x: 0.3 },
    { type: 'car',      z: 3940, x: -0.2, speed: -0.05 },
    { type: 'sinkhole', z: 3970, x: 0.0, width: 0.5 },
  ],

  collectibles: [
    // Tutorial zone — encourage exploration
    { type: 'coin', z: 130, x: 0.0 },
    { type: 'coin', z: 135, x: 0.2 },
    { type: 'coin', z: 140, x: 0.4 },
    { type: 'coin', z: 230, x: -0.3 },
    { type: 'coin', z: 330, x: 0.5 },
    { type: 'coin', z: 430, x: -0.2 },
    { type: 'food', z: 520, x: 0.0 },
    // Main game
    { type: 'coin', z: 900, x: -0.5 },
    { type: 'coin', z: 905, x: -0.3 },
    { type: 'coin', z: 910, x: -0.1 },
    { type: 'food', z: 1100, x: 0.4 },
    { type: 'coin', z: 1300, x: 0.0 },
    { type: 'coin', z: 1305, x: 0.2 },
    { type: 'coin', z: 1500, x: -0.5 },
    { type: 'food', z: 1700, x: 0.3 },
    { type: 'coin', z: 1900, x: -0.2 },
    { type: 'coin', z: 1905, x: 0.0 },
    { type: 'coin', z: 1910, x: 0.2 },
    // Post checkpoint
    { type: 'food', z: 2100, x: -0.4 },
    { type: 'coin', z: 2280, x: 0.5 },
    // Advanced
    { type: 'coin', z: 2520, x: -0.6 },
    { type: 'food', z: 2760, x: 0.4 },
    { type: 'coin', z: 2900, x: 0.0 },
    { type: 'coin', z: 3050, x: -0.3 },
    { type: 'food', z: 3250, x: 0.5 },
    { type: 'coin', z: 3400, x: -0.1 },
    // Climax
    { type: 'food', z: 3650, x: -0.4 },
    { type: 'coin', z: 3750, x: 0.6 },
    { type: 'coin', z: 3850, x: -0.5 },
    { type: 'food', z: 3950, x: 0.0 },
  ],

  curves: [
    { zStart: 600,  zEnd: 900,  direction: 1,  intensity: 0.2 },
    { zStart: 1400, zEnd: 1800, direction: -1, intensity: 0.3 },
    { zStart: 2200, zEnd: 2600, direction: 1,  intensity: 0.25 },
    { zStart: 3000, zEnd: 3400, direction: -1, intensity: 0.35 },
    { zStart: 3700, zEnd: 3950, direction: 1,  intensity: 0.4 },
  ],
};

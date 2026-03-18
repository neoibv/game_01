export const GAME_CONFIG = {
  width: 1280,
  height: 720,

  // Pseudo-3D perspective settings
  perspective: {
    horizonY: 0.35,        // horizon at 35% of screen height
    playerScreenY: 0.82,   // player fixed at 82% of screen height
    roadWidth: 800,        // road width at closest point (px)
    vanishingX: 0.5,       // vanishing point at center X (ratio)
    drawDistance: 300,      // how far ahead to render (Z units)
    fogStart: 200,         // Z distance where fog begins
    stripCount: 180,       // number of horizontal road strips
    perspectiveFactor: 0.007, // controls perspective intensity
  },

  player: {
    moveSpeed: 400,        // left/right movement speed (world units/s)
    jumpHeight: 120,       // max jump height (px on screen)
    jumpDuration: 0.5,     // jump arc duration (seconds)
    lives: 3,
    invincibleDuration: 1500, // ms
    halfWidth: 40,         // collision half-width in world X
  },

  scroll: {
    baseSpeed: 80,         // Z units per second (forward speed)
    maxSpeed: 160,
    speedIncrement: 12,
    incrementInterval: 0.2, // every 20% of stage
  },

  timer: {
    stageTimeLimit: 120,   // seconds
    checkpointBonus: 15,   // seconds added at checkpoint
    timeBonusMultiplier: 100, // remaining seconds × this = bonus score
  },

  score: {
    distanceMultiplier: 10,
    coinPoints: 100,
    foodPoints: 300,
    lifeBonusPerLife: 500,
  },

  collision: {
    zThreshold: 8,         // Z proximity for collision detection
    jumpSafeHeight: 30,    // min jumpHeight to clear obstacles
  },
};

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
    moveSpeed: 550,        // left/right movement speed (world units/s)
    jumpHeight: 120,       // max jump height (px on screen)
    jumpDuration: 0.5,     // jump arc duration (seconds)
    lives: 3,
    invincibleDuration: 1500, // ms
    halfWidth: 40,         // collision half-width in world X
  },

  scroll: {
    baseSpeed: 140,        // Z units per second (forward speed)
    maxSpeed: 350,
    rampDuration: 90,      // seconds to reach max speed (time-based acceleration)
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

  // Visual settings for enhanced procedural graphics
  visual: {
    playerRunFrameRate: 0.15,  // seconds per run frame
    coinRotationRate: 0.12,    // seconds per coin rotation frame
    sparkParticleCount: 10,    // particles on coin collection
    dustEnabled: true,         // dust trail behind player
    hitFlashDuration: 300,     // ms for red screen flash on hit
  },

  // Roadside buildings
  buildings: {
    segmentLength: 30,         // Z units per building segment
    minHeight: 40,             // min building height (px at closest)
    maxHeight: 150,            // max building height
    colors: [0x556677, 0x667788, 0x445566, 0x5A6A7A, 0x4A5A6A],
    windowColor: 0xFFFF88,
    windowAlpha: 0.5,
    windowSpacingX: 12,        // px between windows horizontally
    windowSpacingY: 14,        // px between windows vertically
    roofLineColor: 0x3A4A5A,
  },
};

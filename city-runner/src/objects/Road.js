import { GAME_CONFIG } from '../config/gameConfig.js';

const P = GAME_CONFIG.perspective;
const W = GAME_CONFIG.width;
const H = GAME_CONFIG.height;

const HORIZON_Y = Math.floor(H * P.horizonY);
const PLAYER_Y = Math.floor(H * P.playerScreenY);
const VANISHING_X = Math.floor(W * P.vanishingX);
const ROAD_HALF = P.roadWidth / 2;

// Colors
const ROAD_DARK = 0x666666;
const ROAD_LIGHT = 0x777777;
const CURB_COLOR = 0xCCCCCC;
const LINE_YELLOW = 0xFFDD00;
const GRASS_DARK = 0x446644;
const GRASS_LIGHT = 0x558855;
const SIDEWALK_COLOR = 0xBBBBAA;
const CROSSWALK_COLOR = 0xEEEEEE;

export class Road {
  constructor(scene) {
    this.scene = scene;
    this.graphics = scene.add.graphics();
    this.graphics.setDepth(1);

    // Curve data from stage
    this.curves = [];
  }

  setCurves(curves) {
    this.curves = curves || [];
  }

  /**
   * Project a world position (worldX, worldZ) to screen coordinates.
   * worldX: lateral offset from road center (-ROAD_HALF to +ROAD_HALF range)
   * worldZ: depth (0 = player position, positive = further ahead)
   * Returns { screenX, screenY, scale } or null if behind camera / too far.
   */
  project(worldX, worldZ) {
    if (worldZ < -5) return null; // behind player
    const scale = 1 / (1 + Math.max(0, worldZ) * P.perspectiveFactor);
    const screenY = HORIZON_Y + (PLAYER_Y - HORIZON_Y) * scale;
    const curveOff = this._getCurveOffset(worldZ);
    const screenX = VANISHING_X + (worldX + curveOff) * scale;
    return { screenX, screenY, scale };
  }

  /**
   * Render the road each frame.
   * @param {number} cameraZ - how far the camera has traveled (total distance)
   */
  render(cameraZ) {
    const gfx = this.graphics;
    gfx.clear();

    const stripH = Math.ceil((PLAYER_Y - HORIZON_Y) / P.stripCount);
    const segmentLength = P.drawDistance / P.stripCount;

    for (let i = P.stripCount - 1; i >= 0; i--) {
      const screenY = HORIZON_Y + i * stripH;
      // Map screen strip to Z depth
      const t = i / P.stripCount; // 0 = horizon, 1 = player
      // Inverse perspective to get Z from screen position
      const scale = t; // linear approximation: near strips have scale→1
      const z = (1 / Math.max(0.001, scale) - 1) / P.perspectiveFactor;

      const worldZ = z; // relative to camera
      const absZ = cameraZ + worldZ; // absolute world Z (for stripe pattern)

      // Road width at this depth
      const s = 1 / (1 + z * P.perspectiveFactor);
      const roadW = P.roadWidth * s;
      const curveOff = this._getCurveOffset(worldZ) * s;
      const cx = VANISHING_X + curveOff; // road center X

      // Alternating road/grass color (based on absolute Z for scrolling effect)
      const segment = Math.floor(absZ / 6);
      const isAlt = segment % 2 === 0;

      // Draw ground (full width)
      gfx.fillStyle(isAlt ? GRASS_DARK : GRASS_LIGHT);
      gfx.fillRect(0, screenY, W, stripH + 1);

      // Draw road surface
      gfx.fillStyle(isAlt ? ROAD_DARK : ROAD_LIGHT);
      gfx.fillRect(cx - roadW / 2, screenY, roadW, stripH + 1);

      // Sidewalks (between curb and grass)
      const sidewalkW = Math.max(3, 20 * s);
      gfx.fillStyle(isAlt ? SIDEWALK_COLOR : 0xAAAA99);
      gfx.fillRect(cx - roadW / 2 - sidewalkW, screenY, sidewalkW, stripH + 1);
      gfx.fillRect(cx + roadW / 2, screenY, sidewalkW, stripH + 1);

      // Curb lines (road edges)
      const curbW = Math.max(2, 6 * s);
      if (isAlt) {
        gfx.fillStyle(CURB_COLOR);
        gfx.fillRect(cx - roadW / 2 - curbW / 2, screenY, curbW, stripH + 1);
        gfx.fillRect(cx + roadW / 2 - curbW / 2, screenY, curbW, stripH + 1);
      }

      // Center dashed double yellow line
      const dashSeg = Math.floor(absZ / 3);
      if (dashSeg % 2 === 0) {
        const lineW = Math.max(1, 3 * s);
        const gap = Math.max(1, 2 * s);
        gfx.fillStyle(LINE_YELLOW);
        gfx.fillRect(cx - gap / 2 - lineW, screenY, lineW, stripH + 1);
        gfx.fillRect(cx + gap / 2, screenY, lineW, stripH + 1);
      }

      // Crosswalk segments at specific Z intervals
      const crosswalkSeg = Math.floor(absZ / 1.5);
      const crosswalkPattern = Math.floor(absZ) % 200;
      if (crosswalkPattern >= 0 && crosswalkPattern < 8 && s > 0.05) {
        const stripeCount = 6;
        const stripeW = roadW / (stripeCount * 2);
        gfx.fillStyle(CROSSWALK_COLOR, 0.8);
        for (let ci = 0; ci < stripeCount; ci++) {
          const sx2 = cx - roadW / 2 + ci * stripeW * 2 + stripeW * 0.5;
          gfx.fillRect(sx2, screenY, stripeW, stripH + 1);
        }
      }

      // Fog effect (fade to sky color at distance)
      if (z > P.fogStart) {
        const fogAlpha = Math.min(0.9, (z - P.fogStart) / (P.drawDistance - P.fogStart));
        gfx.fillStyle(0x87CEEB, fogAlpha);
        gfx.fillRect(0, screenY, W, stripH + 1);
      }
    }
  }

  /**
   * Get curve offset for a given Z depth.
   * Returns worldX offset to apply to road center.
   */
  _getCurveOffset(z) {
    let offset = 0;
    for (const curve of this.curves) {
      if (z >= curve.zStart && z <= curve.zEnd) {
        const progress = (z - curve.zStart) / (curve.zEnd - curve.zStart);
        offset += Math.sin(progress * Math.PI) * curve.intensity * ROAD_HALF * curve.direction;
      }
    }
    return offset;
  }

  /**
   * Get the road half-width in world units (for clamping player position).
   */
  getRoadHalfWidth() {
    return ROAD_HALF;
  }

  getHorizonY() {
    return HORIZON_Y;
  }

  getPlayerScreenY() {
    return PLAYER_Y;
  }

  getVanishingX() {
    return VANISHING_X;
  }

  destroy() {
    this.graphics.destroy();
  }
}

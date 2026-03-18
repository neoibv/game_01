import { GAME_CONFIG } from '../config/gameConfig.js';

const P = GAME_CONFIG.perspective;
const B = GAME_CONFIG.buildings;
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

    // Pre-compute building data using LCG for deterministic randomness
    this._buildingCache = {};
  }

  setCurves(curves) {
    this.curves = curves || [];
  }

  project(worldX, worldZ) {
    if (worldZ < -5) return null;
    const scale = 1 / (1 + Math.max(0, worldZ) * P.perspectiveFactor);
    const screenY = HORIZON_Y + (PLAYER_Y - HORIZON_Y) * scale;
    const curveOff = this._getCurveOffset(worldZ);
    const screenX = VANISHING_X + (worldX + curveOff) * scale;
    return { screenX, screenY, scale };
  }

  render(cameraZ) {
    const gfx = this.graphics;
    gfx.clear();

    const stripH = Math.ceil((PLAYER_Y - HORIZON_Y) / P.stripCount);
    const segmentLength = P.drawDistance / P.stripCount;

    for (let i = P.stripCount - 1; i >= 0; i--) {
      const screenY = HORIZON_Y + i * stripH;
      const t = i / P.stripCount;
      const scale = t;
      const z = (1 / Math.max(0.001, scale) - 1) / P.perspectiveFactor;

      const worldZ = z;
      const absZ = cameraZ + worldZ;

      const s = 1 / (1 + z * P.perspectiveFactor);
      const roadW = P.roadWidth * s;
      const curveOff = this._getCurveOffset(worldZ) * s;
      const cx = VANISHING_X + curveOff;

      const segment = Math.floor(absZ / 6);
      const isAlt = segment % 2 === 0;

      // Draw ground (full width)
      gfx.fillStyle(isAlt ? GRASS_DARK : GRASS_LIGHT);
      gfx.fillRect(0, screenY, W, stripH + 1);

      // --- Roadside buildings (behind sidewalk, both sides) ---
      this._renderBuildingStrip(gfx, absZ, s, cx, roadW, screenY, stripH);

      // Draw road surface
      gfx.fillStyle(isAlt ? ROAD_DARK : ROAD_LIGHT);
      gfx.fillRect(cx - roadW / 2, screenY, roadW, stripH + 1);

      // Sidewalks
      const sidewalkW = Math.max(3, 20 * s);
      gfx.fillStyle(isAlt ? SIDEWALK_COLOR : 0xAAAA99);
      gfx.fillRect(cx - roadW / 2 - sidewalkW, screenY, sidewalkW, stripH + 1);
      gfx.fillRect(cx + roadW / 2, screenY, sidewalkW, stripH + 1);

      // Curb lines
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

      // Crosswalk
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

      // Fog effect
      if (z > P.fogStart) {
        const fogAlpha = Math.min(0.9, (z - P.fogStart) / (P.drawDistance - P.fogStart));
        gfx.fillStyle(0x87CEEB, fogAlpha);
        gfx.fillRect(0, screenY, W, stripH + 1);
      }
    }
  }

  /**
   * Render building facades on both sides of the road for a single strip.
   */
  _renderBuildingStrip(gfx, absZ, s, cx, roadW, screenY, stripH) {
    // Only render buildings if close enough to see
    if (s < 0.03) return;

    const sidewalkW = Math.max(3, 20 * s);

    // Building boundaries: from sidewalk edge to screen edge
    const leftBuildingEnd = cx - roadW / 2 - sidewalkW;
    const rightBuildingStart = cx + roadW / 2 + sidewalkW;

    // Determine which building segment this Z falls into
    const buildingSeg = Math.floor(absZ / B.segmentLength);
    const buildingProgress = (absZ % B.segmentLength) / B.segmentLength;

    // Get building data for this segment (deterministic via LCG)
    const bDataLeft = this._getBuildingData(buildingSeg, 0);
    const bDataRight = this._getBuildingData(buildingSeg, 1);

    // Left building wall
    if (leftBuildingEnd > 0) {
      gfx.fillStyle(bDataLeft.color);
      gfx.fillRect(0, screenY, leftBuildingEnd, stripH + 1);

      // Building boundary line (vertical edge between buildings)
      if (buildingProgress < 0.05 && s > 0.06) {
        gfx.fillStyle(0x333344, 0.6);
        gfx.fillRect(leftBuildingEnd - 2, screenY, 2, stripH + 1);
      }

      // Windows on left building
      this._renderWindows(gfx, 0, leftBuildingEnd, screenY, stripH, s, absZ);
    }

    // Right building wall
    if (rightBuildingStart < W) {
      gfx.fillStyle(bDataRight.color);
      gfx.fillRect(rightBuildingStart, screenY, W - rightBuildingStart, stripH + 1);

      // Building boundary line
      if (buildingProgress < 0.05 && s > 0.06) {
        gfx.fillStyle(0x333344, 0.6);
        gfx.fillRect(rightBuildingStart, screenY, 2, stripH + 1);
      }

      // Windows on right building
      this._renderWindows(gfx, rightBuildingStart, W, screenY, stripH, s, absZ);
    }
  }

  /**
   * Render window dots on a building strip.
   */
  _renderWindows(gfx, xStart, xEnd, screenY, stripH, s, absZ) {
    if (s < 0.06) return; // too far for windows

    const spacing = B.windowSpacingX * s;
    if (spacing < 3) return; // too small to see

    const windowSeg = Math.floor(absZ / (B.windowSpacingY * 0.5));
    if (windowSeg % 2 !== 0) return; // alternating rows (gives grid effect with scrolling)

    const winW = Math.max(2, 4 * s);
    const winH = Math.max(1, Math.min(stripH, 3 * s));

    gfx.fillStyle(B.windowColor, B.windowAlpha * s);

    // Use deterministic pattern based on absZ for which windows are "lit"
    const seed = Math.floor(absZ / 3);
    let rng = seed * 2654435761;

    for (let x = xStart + spacing * 0.5; x < xEnd - spacing * 0.3; x += spacing) {
      rng = (rng * 1664525 + 1013904223) & 0xFFFFFFFF;
      if ((rng >>> 0) / 0xFFFFFFFF > 0.45) {
        gfx.fillRect(x, screenY + (stripH - winH) * 0.5, winW, winH);
      }
    }
  }

  /**
   * Get deterministic building data for a given segment index and side (0=left, 1=right).
   */
  _getBuildingData(segIndex, side) {
    const key = segIndex * 2 + side;
    if (this._buildingCache[key]) return this._buildingCache[key];

    // LCG pseudo-random based on segment index + side
    let rng = (key * 1664525 + 1013904223) & 0xFFFFFFFF;
    const rand = () => { rng = (rng * 1664525 + 1013904223) & 0xFFFFFFFF; return (rng >>> 0) / 0xFFFFFFFF; };

    const colorIdx = Math.floor(rand() * B.colors.length);
    // Slight color variation
    const baseColor = B.colors[colorIdx];
    const r = (baseColor >> 16) & 0xFF;
    const g = (baseColor >> 8) & 0xFF;
    const b = baseColor & 0xFF;
    const variation = Math.floor((rand() - 0.5) * 20);
    const color = Phaser.Display.Color.GetColor(
      Math.max(0, Math.min(255, r + variation)),
      Math.max(0, Math.min(255, g + variation)),
      Math.max(0, Math.min(255, b + variation))
    );

    const data = { color, height: B.minHeight + rand() * (B.maxHeight - B.minHeight) };
    this._buildingCache[key] = data;

    // Limit cache size
    const keys = Object.keys(this._buildingCache);
    if (keys.length > 200) {
      for (let i = 0; i < 50; i++) delete this._buildingCache[keys[i]];
    }

    return data;
  }

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

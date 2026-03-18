import { GAME_CONFIG } from '../config/gameConfig.js';

const OBSTACLE_COLORS = {
  sinkhole: 0x111111,
  car: 0xCC2200,
  barrier: 0xFF6600,
  trashcan: 0x228844,
};

const OBSTACLE_SIZES = {
  sinkhole: { w: 0.5, h: 0 },    // width as ratio of road, h=0 (flat on ground)
  car:      { w: 80, h: 44 },
  barrier:  { w: 52, h: 56 },
  trashcan: { w: 36, h: 44 },
};

const COLLECTIBLE_COLORS = {
  coin: 0xFFDD00,
  food: 0xFF8844,
};

export class ObstacleManager {
  constructor(scene, road, stageData) {
    this.scene = scene;
    this.road = road;
    this.stageData = stageData;

    // Active obstacles and collectibles (spawned, not yet passed)
    this.obstacles = [];
    this.collectibles = [];

    // Track next spawn index
    this._nextObstacleIdx = 0;
    this._nextCollectibleIdx = 0;

    // Sort stage data by Z
    this.stageData.obstacles.sort((a, b) => a.z - b.z);
    if (this.stageData.collectibles) {
      this.stageData.collectibles.sort((a, b) => a.z - b.z);
    }
  }

  update(dt, cameraZ, scrollSpeed) {
    const lookAhead = GAME_CONFIG.perspective.drawDistance;

    // Spawn obstacles that are now within draw distance
    const stageObs = this.stageData.obstacles;
    while (
      this._nextObstacleIdx < stageObs.length &&
      stageObs[this._nextObstacleIdx].z <= cameraZ + lookAhead
    ) {
      const def = stageObs[this._nextObstacleIdx];
      this._nextObstacleIdx++;

      // Only spawn if still ahead of player
      if (def.z > cameraZ - 10) {
        const roadHalf = this.road.getRoadHalfWidth();
        const worldX = def.x * roadHalf; // x is normalized -1..1
        const relZ = def.z - cameraZ;
        this.obstacles.push({
          type: def.type,
          worldX,
          worldZ: def.z,       // absolute Z position in stage
          width: def.width || OBSTACLE_SIZES[def.type].w,
          height: OBSTACLE_SIZES[def.type].h,
          color: OBSTACLE_COLORS[def.type],
          speed: def.speed || 0,
          active: true,
          lethal: def.type === 'sinkhole',
        });
      }
    }

    // Spawn collectibles
    const stageColl = this.stageData.collectibles || [];
    while (
      this._nextCollectibleIdx < stageColl.length &&
      stageColl[this._nextCollectibleIdx].z <= cameraZ + lookAhead
    ) {
      const def = stageColl[this._nextCollectibleIdx];
      this._nextCollectibleIdx++;
      if (def.z > cameraZ - 10) {
        const roadHalf = this.road.getRoadHalfWidth();
        this.collectibles.push({
          type: def.type,
          worldX: def.x * roadHalf,
          worldZ: def.z,
          color: COLLECTIBLE_COLORS[def.type] || 0xFFDD00,
          points: def.type === 'food' ? GAME_CONFIG.score.foodPoints : GAME_CONFIG.score.coinPoints,
          active: true,
          bobPhase: Math.random() * Math.PI * 2,
        });
      }
    }

    // Update car movement (lateral)
    for (const obs of this.obstacles) {
      if (!obs.active) continue;
      if (obs.speed) {
        obs.worldX += obs.speed * scrollSpeed * dt;
        // Bounce off road edges
        const roadHalf = this.road.getRoadHalfWidth();
        if (Math.abs(obs.worldX) > roadHalf * 0.8) {
          obs.speed = -obs.speed;
        }
      }
    }

    // Deactivate obstacles/collectibles that are behind the player
    for (const obs of this.obstacles) {
      if (obs.worldZ < cameraZ - 20) obs.active = false;
    }
    for (const col of this.collectibles) {
      if (col.worldZ < cameraZ - 20) col.active = false;
    }

    // Cleanup old inactive entries periodically
    if (this.obstacles.length > 100) {
      this.obstacles = this.obstacles.filter(o => o.active);
    }
    if (this.collectibles.length > 50) {
      this.collectibles = this.collectibles.filter(c => c.active);
    }
  }

  render(gfx, cameraZ) {
    // Collect all renderable objects, sort by Z descending (far first)
    const renderList = [];

    for (const obs of this.obstacles) {
      if (!obs.active) continue;
      const relZ = obs.worldZ - cameraZ;
      if (relZ < -5 || relZ > GAME_CONFIG.perspective.drawDistance) continue;
      renderList.push({ ...obs, relZ, isCollectible: false });
    }

    for (const col of this.collectibles) {
      if (!col.active) continue;
      const relZ = col.worldZ - cameraZ;
      if (relZ < -5 || relZ > GAME_CONFIG.perspective.drawDistance) continue;
      renderList.push({ ...col, relZ, isCollectible: true });
    }

    // Sort far-to-near (painter's algorithm)
    renderList.sort((a, b) => b.relZ - a.relZ);

    for (const item of renderList) {
      const proj = this.road.project(item.worldX, item.relZ);
      if (!proj || proj.scale < 0.01) continue;

      if (item.isCollectible) {
        this._renderCollectible(gfx, item, proj);
      } else {
        this._renderObstacle(gfx, item, proj);
      }
    }
  }

  _renderObstacle(gfx, obs, proj) {
    const s = proj.scale;

    if (obs.type === 'sinkhole') {
      // Sinkhole: dark rectangle on road surface
      const roadHalf = this.road.getRoadHalfWidth();
      const w = (typeof obs.width === 'number' && obs.width <= 1)
        ? obs.width * roadHalf * 2 * s
        : obs.width * s;
      const h = Math.max(4, 20 * s);
      gfx.fillStyle(obs.color, 0.9);
      gfx.fillRect(proj.screenX - w / 2, proj.screenY - h / 2, w, h);
      // Dark edge
      gfx.fillStyle(0x000000, 0.5);
      gfx.fillRect(proj.screenX - w / 2, proj.screenY - h / 2, w, Math.max(2, 4 * s));
    } else {
      // Solid obstacle: scaled rectangle
      const w = obs.width * s;
      const h = obs.height * s;

      // Shadow
      gfx.fillStyle(0x000000, 0.25);
      gfx.fillEllipse(proj.screenX, proj.screenY + 2, w * 0.8, Math.max(3, 6 * s));

      // Body
      gfx.fillStyle(obs.color);
      gfx.fillRect(proj.screenX - w / 2, proj.screenY - h, w, h);

      // Highlight stripe (for car)
      if (obs.type === 'car') {
        gfx.fillStyle(0xFFFFFF, 0.3);
        gfx.fillRect(proj.screenX - w / 2, proj.screenY - h, w, Math.max(2, 4 * s));
      }
    }
  }

  _renderCollectible(gfx, col, proj) {
    const s = proj.scale;
    const r = Math.max(4, 14 * s);
    // Bobbing animation
    const bob = Math.sin(col.bobPhase + this.scene.time.now * 0.004) * 8 * s;
    const y = proj.screenY - 30 * s + bob;

    // Glow
    gfx.fillStyle(col.color, 0.3);
    gfx.fillCircle(proj.screenX, y, r * 1.5);

    // Body
    gfx.fillStyle(col.color);
    gfx.fillCircle(proj.screenX, y, r);

    // Shine
    gfx.fillStyle(0xFFFFFF, 0.5);
    gfx.fillCircle(proj.screenX - r * 0.25, y - r * 0.25, r * 0.35);
  }

  checkCollision(player) {
    const pH = player.getHitbox();
    const cameraZ = this.scene.cameraZ;
    const zThresh = GAME_CONFIG.collision.zThreshold;
    const jumpSafe = GAME_CONFIG.collision.jumpSafeHeight;

    // Check collectibles first
    for (const col of this.collectibles) {
      if (!col.active) continue;
      const relZ = col.worldZ - cameraZ;
      if (Math.abs(relZ) > zThresh * 1.5) continue;

      const roadHalf = this.road.getRoadHalfWidth();
      const colHalf = 25; // collectible pickup radius in world X
      if (pH.xMax > col.worldX - colHalf && pH.xMin < col.worldX + colHalf) {
        col.active = false;
        return { type: 'collectible', points: col.points };
      }
    }

    // Check obstacles
    for (const obs of this.obstacles) {
      if (!obs.active) continue;
      const relZ = obs.worldZ - cameraZ;
      if (Math.abs(relZ) > zThresh) continue;

      // X overlap check
      let obsHalfW;
      if (obs.type === 'sinkhole') {
        const roadHalf = this.road.getRoadHalfWidth();
        obsHalfW = (typeof obs.width === 'number' && obs.width <= 1)
          ? obs.width * roadHalf
          : obs.width / 2;
      } else {
        obsHalfW = obs.width / 2;
      }

      const oxMin = obs.worldX - obsHalfW;
      const oxMax = obs.worldX + obsHalfW;

      if (pH.xMax < oxMin || pH.xMin > oxMax) continue;

      // Jump check: if jumping high enough, clear non-sinkhole obstacles
      if (obs.type === 'sinkhole') {
        // Sinkhole: must jump to avoid
        if (pH.jumpHeight > jumpSafe) continue; // safely jumping over
        return { type: 'obstacle', lethal: true, obstacleType: obs.type };
      } else {
        // Other obstacles: jump over them
        if (pH.jumpHeight > jumpSafe) continue;
        return { type: 'obstacle', lethal: false, obstacleType: obs.type };
      }
    }

    return null;
  }
}

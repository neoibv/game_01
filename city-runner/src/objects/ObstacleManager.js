import { GAME_CONFIG } from '../config/gameConfig.js';

const OBSTACLE_SIZES = {
  sinkhole: { w: 0.5, h: 0 },    // width as ratio of road, h=0 (flat on ground)
  car:      { w: 80, h: 44 },
  barrier:  { w: 52, h: 56 },
  trashcan: { w: 36, h: 44 },
};

const TEXTURE_KEYS = {
  sinkhole: 'sinkhole',
  car: 'car_rear',
  barrier: 'barrier',
  trashcan: 'trashcan',
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

    // Coin animation
    this._coinFrame = 0;
    this._coinTimer = 0;

    // Shadow graphics (shared, lightweight)
    this.shadowGfx = scene.add.graphics();
    this.shadowGfx.setDepth(1.5);

    // Sort stage data by Z
    this.stageData.obstacles.sort((a, b) => a.z - b.z);
    if (this.stageData.collectibles) {
      this.stageData.collectibles.sort((a, b) => a.z - b.z);
    }
  }

  update(dt, cameraZ, scrollSpeed) {
    const lookAhead = GAME_CONFIG.perspective.drawDistance;

    // Coin rotation animation
    this._coinTimer += dt;
    if (this._coinTimer >= 0.12) {
      this._coinTimer = 0;
      this._coinFrame = (this._coinFrame + 1) % 4;
    }

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
        const worldX = def.x * roadHalf;
        const textureKey = TEXTURE_KEYS[def.type];
        const image = this.scene.add.image(0, 0, textureKey);
        image.setDepth(2);
        image.setVisible(false);
        // Sinkhole: anchor at center; others: anchor at bottom center
        if (def.type === 'sinkhole') {
          image.setOrigin(0.5, 0.5);
        } else {
          image.setOrigin(0.5, 1);
        }

        this.obstacles.push({
          type: def.type,
          worldX,
          worldZ: def.z,
          width: def.width || OBSTACLE_SIZES[def.type].w,
          height: OBSTACLE_SIZES[def.type].h,
          speed: def.speed || 0,
          active: true,
          lethal: def.type === 'sinkhole',
          image,
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
        const textureKey = def.type === 'food' ? 'food_tteokbokki' : 'coin_1';
        const image = this.scene.add.image(0, 0, textureKey);
        image.setDepth(2);
        image.setOrigin(0.5, 0.5);
        image.setVisible(false);

        this.collectibles.push({
          type: def.type,
          worldX: def.x * roadHalf,
          worldZ: def.z,
          points: def.type === 'food' ? GAME_CONFIG.score.foodPoints : GAME_CONFIG.score.coinPoints,
          active: true,
          bobPhase: Math.random() * Math.PI * 2,
          image,
        });
      }
    }

    // Update car movement (lateral)
    for (const obs of this.obstacles) {
      if (!obs.active) continue;
      if (obs.speed) {
        obs.worldX += obs.speed * scrollSpeed * dt;
        const roadHalf = this.road.getRoadHalfWidth();
        if (Math.abs(obs.worldX) > roadHalf * 0.8) {
          obs.speed = -obs.speed;
        }
      }
    }

    // Deactivate obstacles/collectibles that are behind the player
    for (const obs of this.obstacles) {
      if (obs.worldZ < cameraZ - 20) {
        if (obs.active && obs.image) {
          obs.image.destroy();
          obs.image = null;
        }
        obs.active = false;
      }
    }
    for (const col of this.collectibles) {
      if (col.worldZ < cameraZ - 20) {
        if (col.active && col.image) {
          col.image.destroy();
          col.image = null;
        }
        col.active = false;
      }
    }

    // Cleanup old inactive entries periodically
    if (this.obstacles.length > 100) {
      this.obstacles = this.obstacles.filter(o => o.active);
    }
    if (this.collectibles.length > 50) {
      this.collectibles = this.collectibles.filter(c => c.active);
    }
  }

  render(cameraZ) {
    this.shadowGfx.clear();

    // Collect all renderable objects, sort by Z descending (far first)
    const renderList = [];

    for (const obs of this.obstacles) {
      if (!obs.active) continue;
      const relZ = obs.worldZ - cameraZ;
      if (relZ < -5 || relZ > GAME_CONFIG.perspective.drawDistance) {
        if (obs.image) obs.image.setVisible(false);
        continue;
      }
      renderList.push({ obj: obs, relZ, isCollectible: false });
    }

    for (const col of this.collectibles) {
      if (!col.active) continue;
      const relZ = col.worldZ - cameraZ;
      if (relZ < -5 || relZ > GAME_CONFIG.perspective.drawDistance) {
        if (col.image) col.image.setVisible(false);
        continue;
      }
      renderList.push({ obj: col, relZ, isCollectible: true });
    }

    // Sort far-to-near (painter's algorithm)
    renderList.sort((a, b) => b.relZ - a.relZ);

    for (const item of renderList) {
      const proj = this.road.project(item.obj.worldX, item.relZ);
      if (!proj || proj.scale < 0.01) {
        if (item.obj.image) item.obj.image.setVisible(false);
        continue;
      }

      if (item.isCollectible) {
        this._renderCollectible(item.obj, proj);
      } else {
        this._renderObstacle(item.obj, proj);
      }
    }
  }

  _renderObstacle(obs, proj) {
    const s = proj.scale;
    const img = obs.image;
    if (!img) return;

    if (obs.type === 'sinkhole') {
      // Sinkhole: scale width based on road proportion
      const roadHalf = this.road.getRoadHalfWidth();
      const widthRatio = (typeof obs.width === 'number' && obs.width <= 1) ? obs.width : 0.5;
      const targetW = widthRatio * roadHalf * 2 * s;
      const targetH = Math.max(4, 24 * s);
      img.setDisplaySize(targetW, targetH);
      img.setPosition(proj.screenX, proj.screenY);
    } else {
      // Normal obstacle: scale by perspective
      img.setScale(s);
      img.setPosition(proj.screenX, proj.screenY);

      // Shadow
      const w = (obs.width || 50) * s;
      this.shadowGfx.fillStyle(0x000000, 0.25);
      this.shadowGfx.fillEllipse(proj.screenX, proj.screenY + 2, w * 0.8, Math.max(3, 6 * s));
    }

    // Depth sorting: farther objects render behind
    img.setDepth(2 + (1 - s) * 0.001);
    img.setVisible(true);
  }

  _renderCollectible(col, proj) {
    const s = proj.scale;
    const img = col.image;
    if (!img) return;

    // Bobbing animation
    const bob = Math.sin(col.bobPhase + this.scene.time.now * 0.004) * 8 * s;
    const y = proj.screenY - 30 * s + bob;

    // Update coin rotation frame
    if (col.type === 'coin') {
      img.setTexture(`coin_${this._coinFrame + 1}`);
    }

    img.setScale(s);
    img.setPosition(proj.screenX, y);
    img.setDepth(2 + (1 - s) * 0.001);
    img.setVisible(true);
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

      const colHalf = 25;
      if (pH.xMax > col.worldX - colHalf && pH.xMin < col.worldX + colHalf) {
        // Get screen position for particle effect
        const proj = this.road.project(col.worldX, relZ);
        const screenPos = proj ? { x: proj.screenX, y: proj.screenY - 30 * proj.scale } : null;

        if (col.image) {
          col.image.destroy();
          col.image = null;
        }
        col.active = false;
        return { type: 'collectible', points: col.points, screenPos };
      }
    }

    // Check obstacles
    for (const obs of this.obstacles) {
      if (!obs.active) continue;
      const relZ = obs.worldZ - cameraZ;
      if (Math.abs(relZ) > zThresh) continue;

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

      if (obs.type === 'sinkhole') {
        if (pH.jumpHeight > jumpSafe) continue;
        return { type: 'obstacle', lethal: true, obstacleType: obs.type };
      } else {
        if (pH.jumpHeight > jumpSafe) continue;
        return { type: 'obstacle', lethal: false, obstacleType: obs.type };
      }
    }

    return null;
  }

  destroy() {
    for (const obs of this.obstacles) {
      if (obs.image) obs.image.destroy();
    }
    for (const col of this.collectibles) {
      if (col.image) col.image.destroy();
    }
    this.shadowGfx.destroy();
  }
}

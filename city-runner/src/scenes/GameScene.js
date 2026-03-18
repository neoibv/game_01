import { GAME_CONFIG } from '../config/gameConfig.js';
import { STAGE1_DATA } from '../config/stage1.js';
import { Road } from '../objects/Road.js';
import { Player } from '../objects/Player.js';
import { ObstacleManager } from '../objects/ObstacleManager.js';

const STAGE_MAP = { 1: STAGE1_DATA };
const W = GAME_CONFIG.width;
const H = GAME_CONFIG.height;

export class GameScene extends Phaser.Scene {
  constructor() {
    super({ key: 'GameScene' });
  }

  init(data) {
    this.stageId = data.stageId || 1;
    this.stageData = STAGE_MAP[this.stageId] || STAGE1_DATA;
    this.lives = GAME_CONFIG.player.lives;
    this.score = 0;
    this.cameraZ = 0;          // total distance traveled (Z units)
    this.scrollSpeed = GAME_CONFIG.scroll.baseSpeed;
    this.gameActive = false;
    this.checkpointReached = false;
    this.timeRemaining = GAME_CONFIG.timer.stageTimeLimit;
    this.collectibleScore = 0;
    this.elapsed = 0;             // total elapsed time for speed ramp
  }

  create() {
    // --- Sky background (static, behind everything) ---
    this._createSky();

    // --- City skyline at horizon ---
    this._createSkyline();

    // --- Clouds ---
    this._createClouds();

    // --- Road renderer ---
    this.road = new Road(this);
    this.road.setCurves(this.stageData.curves || []);

    // --- Player ---
    this.player = new Player(this, this.road);

    // --- Obstacle manager ---
    this.obstacleManager = new ObstacleManager(this, this.road, this.stageData);

    // --- Particle emitters ---
    this._createParticles();

    // --- Hit flash overlay ---
    this.hitFlash = this.add.rectangle(W / 2, H / 2, W, H, 0xFF0000, 0);
    this.hitFlash.setDepth(10);

    // --- Input ---
    this.cursors = this.input.keyboard.createCursorKeys();
    this.wasd = this.input.keyboard.addKeys({
      up: Phaser.Input.Keyboard.KeyCodes.W,
      left: Phaser.Input.Keyboard.KeyCodes.A,
      right: Phaser.Input.Keyboard.KeyCodes.D,
      space: Phaser.Input.Keyboard.KeyCodes.SPACE,
    });

    // Mobile: tap left half = left, right half = right, double-tap = jump
    this._lastTapTime = 0;
    this.input.on('pointerdown', (pointer) => {
      if (!this.gameActive) return;
      const now = this.time.now;
      if (now - this._lastTapTime < 300) {
        this.player.jump();
      } else {
        this._touchSide = pointer.x < W / 2 ? 'left' : 'right';
      }
      this._lastTapTime = now;
    });
    this.input.on('pointerup', () => { this._touchSide = null; });

    // --- Launch UIScene ---
    this.scene.launch('UIScene', { gameScene: this });
    this.uiScene = this.scene.get('UIScene');

    // --- Start after brief delay ---
    this.time.delayedCall(500, () => { this.gameActive = true; });
  }

  update(time, delta) {
    if (!this.gameActive) return;
    const dt = delta / 1000;

    // --- Input ---
    const left = this.cursors.left.isDown || this.wasd.left.isDown || this._touchSide === 'left';
    const right = this.cursors.right.isDown || this.wasd.right.isDown || this._touchSide === 'right';
    const jump = Phaser.Input.Keyboard.JustDown(this.cursors.up)
      || Phaser.Input.Keyboard.JustDown(this.wasd.up)
      || Phaser.Input.Keyboard.JustDown(this.wasd.space)
      || Phaser.Input.Keyboard.JustDown(this.cursors.space);

    // --- Player update ---
    this.player.handleInput(left, right, jump);
    this.player.update(dt);

    // --- Speed progression (time-based continuous acceleration) ---
    this.elapsed += dt;
    const rampT = Math.min(1, this.elapsed / GAME_CONFIG.scroll.rampDuration);
    this.scrollSpeed = GAME_CONFIG.scroll.baseSpeed +
      (GAME_CONFIG.scroll.maxSpeed - GAME_CONFIG.scroll.baseSpeed) * rampT;

    // --- Advance camera Z ---
    this.cameraZ += this.scrollSpeed * dt;

    // --- Timer ---
    this.timeRemaining -= dt;
    if (this.timeRemaining <= 0) {
      this.timeRemaining = 0;
      this._gameOver('time');
      return;
    }

    // --- Checkpoint ---
    if (!this.checkpointReached && this.cameraZ >= this.stageData.checkpointZ) {
      this.checkpointReached = true;
      this.timeRemaining += GAME_CONFIG.timer.checkpointBonus;
      if (this.uiScene) this.uiScene.events.emit('checkpoint');
    }

    // --- Stage clear ---
    if (this.cameraZ >= this.stageData.totalDistance) {
      this._stageClear();
      return;
    }

    // --- Obstacle manager update + collision ---
    this.obstacleManager.update(dt, this.cameraZ, this.scrollSpeed);
    this._checkCollisions();

    // --- Score ---
    this.score = Math.floor((this.cameraZ / this.stageData.totalDistance) * this.stageData.totalDistance * GAME_CONFIG.score.distanceMultiplier / 100) + this.collectibleScore;

    // --- Render ---
    this.road.render(this.cameraZ);
    this.obstacleManager.render(this.cameraZ);
    this.player.render();

    // --- Dust particles behind player ---
    if (this.dustEmitter && !this.player.isJumping && this.player.state !== 'dead') {
      const proj = this.road.project(this.player.worldX, 0);
      if (proj) {
        this.dustEmitter.setPosition(proj.screenX, proj.screenY + 2);
        this.dustEmitter.emitParticle(1);
      }
    }

    // --- Update HUD ---
    if (this.uiScene) {
      this.uiScene.events.emit('update-score', this.score);
      this.uiScene.events.emit('update-distance', this.cameraZ);
      this.uiScene.events.emit('update-timer', this.timeRemaining);
      this.uiScene.events.emit('update-lives', this.lives);
    }
  }

  _checkCollisions() {
    if (this.player.isInvincible) return;

    const result = this.obstacleManager.checkCollision(this.player);
    if (!result) return;

    if (result.type === 'collectible') {
      this.collectibleScore += result.points;
      this._playCoinSFX();
      // Spark particles at collection point
      if (this.sparkEmitter && result.screenPos) {
        this.sparkEmitter.setPosition(result.screenPos.x, result.screenPos.y);
        this.sparkEmitter.explode(10);
      }
      return;
    }

    // Obstacle hit
    if (result.lethal) {
      this.lives = 0;
      if (this.uiScene) this.uiScene.events.emit('update-lives', 0);
      this.player.die();
      this._flashHit();
      this._gameOver('sinkhole');
    } else {
      this.lives--;
      this.player.hit();
      this._playHitSFX();
      this._flashHit();
      if (this.uiScene) this.uiScene.events.emit('update-lives', this.lives);
      if (this.lives <= 0) {
        this.player.die();
        this._gameOver('dead');
      }
    }
  }

  _flashHit() {
    this.hitFlash.setAlpha(0.35);
    this.tweens.add({
      targets: this.hitFlash,
      alpha: 0,
      duration: 300,
      ease: 'Power2',
    });
  }

  _gameOver(reason) {
    if (!this.gameActive) return;
    this.gameActive = false;
    this._saveScore();
    this.time.delayedCall(1200, () => {
      this.scene.stop('UIScene');
      this.scene.start('GameOverScene', {
        score: this.score,
        distance: this.cameraZ,
        totalDistance: this.stageData.totalDistance,
        stageId: this.stageId,
        reason,
      });
    });
  }

  _stageClear() {
    if (!this.gameActive) return;
    this.gameActive = false;
    const timeBonus = Math.floor(this.timeRemaining * GAME_CONFIG.timer.timeBonusMultiplier);
    const lifeBonus = this.lives * GAME_CONFIG.score.lifeBonusPerLife;
    const finalScore = this.score + timeBonus + lifeBonus;
    this._saveScore(finalScore);
    if (this.uiScene) this.uiScene.events.emit('stage-clear');
    this.time.delayedCall(1500, () => {
      this.scene.stop('UIScene');
      this.scene.start('StageClearScene', {
        score: finalScore,
        baseScore: this.score,
        timeBonus,
        lifeBonus,
        lives: this.lives,
        timeRemaining: this.timeRemaining,
        distance: this.cameraZ,
        stageId: this.stageId,
      });
    });
  }

  _saveScore(overrideScore) {
    const s = overrideScore !== undefined ? overrideScore : this.score;
    const best = parseInt(localStorage.getItem('cityrunner_best') || '0', 10);
    if (s > best) localStorage.setItem('cityrunner_best', String(s));
  }

  // --- Background layers ---

  _createSky() {
    const sky = this.add.graphics();
    sky.setDepth(0);
    sky.fillGradientStyle(0x87CEEB, 0x87CEEB, 0xFDB97D, 0xFDB97D, 1);
    sky.fillRect(0, 0, W, this.scale.height * 0.5);
    // Lower sky
    sky.fillGradientStyle(0xFDB97D, 0xFDB97D, 0xE8D5B7, 0xE8D5B7, 1);
    sky.fillRect(0, this.scale.height * 0.25, W, this.scale.height * 0.25);

    // Sun
    const sunGfx = this.add.graphics();
    sunGfx.setDepth(0);
    sunGfx.fillStyle(0xFFDD66, 0.3);
    sunGfx.fillCircle(W * 0.8, H * 0.12, 40);
    sunGfx.fillStyle(0xFFEE88, 0.5);
    sunGfx.fillCircle(W * 0.8, H * 0.12, 25);
    sunGfx.fillStyle(0xFFFF99, 0.8);
    sunGfx.fillCircle(W * 0.8, H * 0.12, 14);
  }

  _createClouds() {
    const cloudGfx = this.add.graphics();
    cloudGfx.setDepth(0);

    const clouds = [
      { x: 120, y: 50, w: 100, h: 30 },
      { x: 400, y: 35, w: 140, h: 35 },
      { x: 700, y: 55, w: 90, h: 25 },
      { x: 1000, y: 30, w: 120, h: 32 },
      { x: 1150, y: 60, w: 80, h: 22 },
    ];

    for (const c of clouds) {
      cloudGfx.fillStyle(0xFFFFFF, 0.4);
      cloudGfx.fillEllipse(c.x, c.y, c.w, c.h);
      cloudGfx.fillStyle(0xFFFFFF, 0.6);
      cloudGfx.fillEllipse(c.x - c.w * 0.15, c.y - c.h * 0.1, c.w * 0.6, c.h * 0.7);
    }
  }

  _createSkyline() {
    const gfx = this.add.graphics();
    gfx.setDepth(0);
    const horizonY = Math.floor(H * GAME_CONFIG.perspective.horizonY);

    // Deterministic pseudo-random buildings
    let rng = 7;
    const lcg = () => { rng = (rng * 1664525 + 1013904223) & 0xFFFFFFFF; return (rng >>> 0) / 0xFFFFFFFF; };

    let x = 0;
    while (x < W) {
      const w = 20 + lcg() * 60;
      const h = 20 + lcg() * 80;
      const shade = 0x55 + Math.floor(lcg() * 0x33);
      gfx.fillStyle(Phaser.Display.Color.GetColor(shade, shade + 0x10, shade + 0x20));
      gfx.fillRect(x, horizonY - h, w, h);

      // Antenna/spire on tall buildings
      if (h > 60 && lcg() > 0.4) {
        const antennaH = 8 + lcg() * 15;
        gfx.fillStyle(0x888888);
        gfx.fillRect(x + w / 2 - 1, horizonY - h - antennaH, 2, antennaH);
        // Antenna light
        gfx.fillStyle(0xFF3333, 0.8);
        gfx.fillCircle(x + w / 2, horizonY - h - antennaH, 2);
      }

      // Windows
      gfx.fillStyle(0xFFFF88, 0.4);
      for (let wy = horizonY - h + 5; wy < horizonY - 4; wy += 10) {
        for (let wx = x + 3; wx < x + w - 5; wx += 8) {
          if (lcg() > 0.35) gfx.fillRect(wx, wy, 4, 5);
        }
      }
      x += w + 2 + lcg() * 8;
    }

    // Namsan Tower silhouette (Seoul landmark)
    const towerX = W * 0.35;
    const towerBaseY = horizonY;

    // Mountain/hill base
    gfx.fillStyle(0x556655, 0.7);
    gfx.fillTriangle(
      towerX - 80, towerBaseY,
      towerX, towerBaseY - 40,
      towerX + 80, towerBaseY
    );

    // Tower shaft
    gfx.fillStyle(0x999999);
    gfx.fillRect(towerX - 2, towerBaseY - 90, 4, 50);

    // Tower observation deck
    gfx.fillStyle(0x888888);
    gfx.fillRect(towerX - 8, towerBaseY - 95, 16, 10);

    // Tower tip/antenna
    gfx.fillStyle(0xAAAAAA);
    gfx.fillRect(towerX - 1, towerBaseY - 110, 2, 15);

    // Tower light
    gfx.fillStyle(0xFF4444, 0.9);
    gfx.fillCircle(towerX, towerBaseY - 110, 2);
  }

  // --- Particles ---

  _createParticles() {
    // Coin collection sparks
    this.sparkEmitter = this.add.particles(0, 0, 'particle_spark', {
      speed: { min: 50, max: 150 },
      angle: { min: 0, max: 360 },
      scale: { start: 1, end: 0 },
      lifespan: 400,
      gravityY: 100,
      emitting: false,
    });
    this.sparkEmitter.setDepth(5);

    // Dust trail behind player
    this.dustEmitter = this.add.particles(0, 0, 'particle_dust', {
      speed: { min: 5, max: 20 },
      angle: { min: 250, max: 290 },
      scale: { start: 0.8, end: 0 },
      alpha: { start: 0.5, end: 0 },
      lifespan: 300,
      emitting: false,
    });
    this.dustEmitter.setDepth(1.8);
  }

  // --- SFX ---

  _playHitSFX() {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain); gain.connect(ctx.destination);
      osc.frequency.setValueAtTime(220, ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(80, ctx.currentTime + 0.15);
      gain.gain.setValueAtTime(0.3, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.2);
      osc.start(ctx.currentTime); osc.stop(ctx.currentTime + 0.2);
    } catch (e) { /* ignore */ }
  }

  _playCoinSFX() {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain); gain.connect(ctx.destination);
      osc.type = 'square';
      osc.frequency.setValueAtTime(880, ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(1320, ctx.currentTime + 0.1);
      gain.gain.setValueAtTime(0.15, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.15);
      osc.start(ctx.currentTime); osc.stop(ctx.currentTime + 0.15);
    } catch (e) { /* ignore */ }
  }
}

import { GAME_CONFIG } from '../config/gameConfig.js';

export class Player {
  constructor(scene, road) {
    this.scene = scene;
    this.road = road;

    // World position
    this.worldX = 0; // lateral offset from road center

    // Jump state
    this.jumpHeight = 0;     // current height off ground (px)
    this.isJumping = false;
    this._jumpTime = 0;

    // State
    this.state = 'running';  // running | jumping | hit | dead
    this.isInvincible = false;
    this._invincibleTimer = 0;
    this._blinkTimer = 0;
    this._visible = true;

    // Animation
    this._runFrame = 0;
    this._runTimer = 0;
    this._coinFrame = 0;

    // Sprite image (uses pre-baked textures from TextureFactory)
    this.sprite = scene.add.image(0, 0, 'player_run_1');
    this.sprite.setDepth(3);
    this.sprite.setOrigin(0.5, 1); // anchor at bottom center

    // Shadow graphics (dynamic, changes with jump)
    this.shadowGfx = scene.add.graphics();
    this.shadowGfx.setDepth(2.9);

    // Dimensions (screen size at player position)
    this.drawW = 32;
    this.drawH = 48;
  }

  handleInput(left, right, jump) {
    if (this.state === 'dead') return;
    this._inputLeft = left;
    this._inputRight = right;
    if (jump && !this.isJumping && this.state !== 'hit') {
      this.isJumping = true;
      this._jumpTime = 0;
      this.state = 'jumping';
      this._playJumpSFX();
    }
  }

  update(dt) {
    if (this.state === 'dead') return;

    const roadHalf = this.road.getRoadHalfWidth();
    const speed = GAME_CONFIG.player.moveSpeed;

    // Left/right movement
    if (this._inputLeft) this.worldX -= speed * dt;
    if (this._inputRight) this.worldX += speed * dt;

    // Clamp to road bounds
    const limit = roadHalf - GAME_CONFIG.player.halfWidth;
    this.worldX = Phaser.Math.Clamp(this.worldX, -limit, limit);

    // Jump arc (sine curve)
    if (this.isJumping) {
      this._jumpTime += dt;
      const t = this._jumpTime / GAME_CONFIG.player.jumpDuration;
      if (t >= 1) {
        // Land
        this.isJumping = false;
        this.jumpHeight = 0;
        this._jumpTime = 0;
        if (this.state === 'jumping') this.state = 'running';
      } else {
        this.jumpHeight = Math.sin(t * Math.PI) * GAME_CONFIG.player.jumpHeight;
      }
    }

    // Invincibility
    if (this.isInvincible) {
      this._invincibleTimer -= dt * 1000;
      this._blinkTimer += dt * 1000;
      if (this._blinkTimer >= 100) {
        this._blinkTimer = 0;
        this._visible = !this._visible;
      }
      if (this._invincibleTimer <= 0) {
        this.isInvincible = false;
        this._visible = true;
      }
    }

    // Running animation (alternate leg frames)
    if (this.state === 'running') {
      this._runTimer += dt;
      if (this._runTimer >= 0.15) {
        this._runTimer = 0;
        this._runFrame = this._runFrame === 0 ? 1 : 0;
      }
    }

    // Color state handled by texture selection
    if (this.state === 'hit' && !this.isInvincible) {
      this.state = 'running';
    }
  }

  hit() {
    if (this.isInvincible || this.state === 'dead') return;
    this.isInvincible = true;
    this._invincibleTimer = GAME_CONFIG.player.invincibleDuration;
    this._blinkTimer = 0;
    this.state = 'hit';
  }

  die() {
    this.state = 'dead';
    this._visible = true;
  }

  render() {
    this.shadowGfx.clear();

    if (!this._visible) {
      this.sprite.setVisible(false);
      return;
    }

    // Project player position (Z=0, at player depth)
    const proj = this.road.project(this.worldX, 0);
    if (!proj) {
      this.sprite.setVisible(false);
      return;
    }

    const sx = proj.screenX;
    const sy = proj.screenY - this.jumpHeight;

    // Select texture based on state
    let textureKey;
    if (this.state === 'dead') {
      textureKey = 'player_hit';
    } else if (this.isJumping) {
      textureKey = 'player_jump';
    } else if (this.isInvincible) {
      textureKey = 'player_hit';
    } else {
      textureKey = this._runFrame === 0 ? 'player_run_1' : 'player_run_2';
    }

    this.sprite.setTexture(textureKey);
    this.sprite.setPosition(sx, sy);
    this.sprite.setVisible(true);

    // Shadow (on ground)
    if (this.jumpHeight > 5) {
      const shadowW = this.drawW * (1 - this.jumpHeight / (GAME_CONFIG.player.jumpHeight * 2));
      const shadowH = 8 * (1 - this.jumpHeight / (GAME_CONFIG.player.jumpHeight * 2));
      this.shadowGfx.fillStyle(0x000000, 0.3);
      this.shadowGfx.fillEllipse(sx, proj.screenY + 2, shadowW, shadowH);
    }
  }

  getHitbox() {
    return {
      xMin: this.worldX - GAME_CONFIG.player.halfWidth,
      xMax: this.worldX + GAME_CONFIG.player.halfWidth,
      z: 0,
      jumpHeight: this.jumpHeight,
    };
  }

  _playJumpSFX() {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain); gain.connect(ctx.destination);
      osc.frequency.setValueAtTime(400, ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(800, ctx.currentTime + 0.1);
      gain.gain.setValueAtTime(0.15, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.12);
      osc.start(ctx.currentTime); osc.stop(ctx.currentTime + 0.12);
    } catch (e) { /* ignore */ }
  }
}

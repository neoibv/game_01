import { GAME_CONFIG } from '../config/gameConfig.js';

const COLORS = {
  normal: 0x2255FF,
  jump:   0x66AAFF,
  hit:    0xFF2222,
  dead:   0x888888,
};

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
    this._color = COLORS.normal;

    // Graphics
    this.graphics = scene.add.graphics();
    this.graphics.setDepth(3);

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

    // Color
    if (this.state === 'hit' && !this.isInvincible) {
      this.state = 'running';
    }
    if (this.isJumping) {
      this._color = COLORS.jump;
    } else if (this.isInvincible) {
      this._color = COLORS.hit;
    } else {
      this._color = COLORS.normal;
    }
  }

  hit() {
    if (this.isInvincible || this.state === 'dead') return;
    this.isInvincible = true;
    this._invincibleTimer = GAME_CONFIG.player.invincibleDuration;
    this._blinkTimer = 0;
    this.state = 'hit';
    this._color = COLORS.hit;
  }

  die() {
    this.state = 'dead';
    this._color = COLORS.dead;
    this._visible = true;
  }

  render() {
    const gfx = this.graphics;
    gfx.clear();
    if (!this._visible) return;

    // Project player position (Z=0, at player depth)
    const proj = this.road.project(this.worldX, 0);
    if (!proj) return;

    const sx = proj.screenX;
    const sy = proj.screenY - this.jumpHeight;
    const w = this.drawW;
    const h = this.drawH;

    // Shadow (on ground, always)
    if (this.jumpHeight > 5) {
      const shadowW = w * (1 - this.jumpHeight / (GAME_CONFIG.player.jumpHeight * 2));
      const shadowH = 8 * (1 - this.jumpHeight / (GAME_CONFIG.player.jumpHeight * 2));
      gfx.fillStyle(0x000000, 0.3);
      gfx.fillEllipse(sx, proj.screenY + 2, shadowW, shadowH);
    }

    // Player body
    gfx.fillStyle(this._color);
    gfx.fillRect(sx - w / 2, sy - h, w, h);

    // Eyes (simple)
    gfx.fillStyle(0xFFFFFF);
    gfx.fillRect(sx - 6, sy - h + 10, 6, 6);
    gfx.fillRect(sx + 2, sy - h + 10, 6, 6);
    gfx.fillStyle(0x000000);
    gfx.fillRect(sx - 4, sy - h + 12, 3, 3);
    gfx.fillRect(sx + 4, sy - h + 12, 3, 3);
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

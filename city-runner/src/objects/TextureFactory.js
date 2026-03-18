/**
 * TextureFactory — Generates all game sprite textures procedurally
 * using Phaser Graphics API + generateTexture().
 * Called once in BootScene; textures are reused everywhere.
 */
export class TextureFactory {
  static createAll(scene) {
    TextureFactory._createPlayerTextures(scene);
    TextureFactory._createObstacleTextures(scene);
    TextureFactory._createCollectibleTextures(scene);
    TextureFactory._createParticleTextures(scene);
  }

  // ───────── Player (32×48) ─────────

  static _createPlayerTextures(scene) {
    const W = 32, H = 48;

    // --- Run frame 1 (left leg forward) ---
    TextureFactory._drawPlayer(scene, 'player_run_1', W, H, {
      color: 0x2255FF, legFrame: 0,
    });

    // --- Run frame 2 (right leg forward) ---
    TextureFactory._drawPlayer(scene, 'player_run_2', W, H, {
      color: 0x2255FF, legFrame: 1,
    });

    // --- Jump ---
    TextureFactory._drawPlayer(scene, 'player_jump', W, H, {
      color: 0x66AAFF, jumping: true,
    });

    // --- Hit ---
    TextureFactory._drawPlayer(scene, 'player_hit', W, H, {
      color: 0xFF2222, hit: true,
    });
  }

  static _drawPlayer(scene, key, W, H, opts) {
    const gfx = scene.make.graphics({ add: false });
    const cx = W / 2;

    // Body (torso)
    gfx.fillStyle(opts.color);
    gfx.fillRect(6, 8, 20, 18);

    // Head
    const headColor = opts.hit ? 0xFF4444 : 0x3366FF;
    gfx.fillStyle(headColor);
    gfx.fillRoundedRect(7, 0, 18, 16, 4);

    // Eyes
    gfx.fillStyle(0xFFFFFF);
    gfx.fillRect(10, 4, 5, 5);
    gfx.fillRect(18, 4, 5, 5);
    gfx.fillStyle(0x111111);
    gfx.fillRect(12, 6, 3, 3);
    gfx.fillRect(20, 6, 3, 3);

    // Arms
    const armColor = Phaser.Display.Color.IntegerToColor(opts.color).darken(15).color;
    gfx.fillStyle(armColor);
    if (opts.jumping) {
      // Arms raised
      gfx.fillRect(2, 4, 5, 12);
      gfx.fillRect(25, 4, 5, 12);
    } else {
      // Arms at sides, slightly different per frame
      const armOff = opts.legFrame === 0 ? 2 : -1;
      gfx.fillRect(1, 10 + armOff, 5, 14);
      gfx.fillRect(26, 10 - armOff, 5, 14);
    }

    // Legs
    const legColor = Phaser.Display.Color.IntegerToColor(opts.color).darken(25).color;
    gfx.fillStyle(legColor);
    if (opts.jumping) {
      // Tucked legs
      gfx.fillRect(8, 26, 7, 12);
      gfx.fillRect(17, 26, 7, 12);
    } else if (opts.legFrame === 0) {
      // Left leg forward, right back
      gfx.fillRect(7, 26, 7, 18);
      gfx.fillRect(18, 26, 7, 14);
      // Shoes
      gfx.fillStyle(0xDDDDDD);
      gfx.fillRect(6, 42, 9, 5);
      gfx.fillRect(17, 38, 9, 5);
    } else {
      // Right leg forward, left back
      gfx.fillRect(7, 26, 7, 14);
      gfx.fillRect(18, 26, 7, 18);
      gfx.fillStyle(0xDDDDDD);
      gfx.fillRect(6, 38, 9, 5);
      gfx.fillRect(17, 42, 9, 5);
    }

    // Outline
    gfx.lineStyle(1, 0x000000, 0.4);
    gfx.strokeRect(6, 8, 20, 18);

    gfx.generateTexture(key, W, H);
    gfx.destroy();
  }

  // ───────── Obstacles ─────────

  static _createObstacleTextures(scene) {
    TextureFactory._createCarTexture(scene);
    TextureFactory._createBarrierTexture(scene);
    TextureFactory._createTrashcanTexture(scene);
    TextureFactory._createSinkholeTexture(scene);
  }

  static _createCarTexture(scene) {
    const W = 80, H = 44;
    const gfx = scene.make.graphics({ add: false });

    // Car body (main)
    gfx.fillStyle(0xCC2200);
    gfx.fillRoundedRect(4, 6, 72, 28, 3);

    // Roof / windshield (lighter top area)
    gfx.fillStyle(0x88CCEE, 0.6);
    gfx.fillRoundedRect(18, 2, 44, 14, 3);

    // Windshield frame
    gfx.lineStyle(1, 0x333333, 0.8);
    gfx.strokeRoundedRect(18, 2, 44, 14, 3);

    // Body darker bottom (underbody)
    gfx.fillStyle(0x881100);
    gfx.fillRect(6, 28, 68, 8);

    // Rear lights
    gfx.fillStyle(0xFF4400);
    gfx.fillRect(6, 10, 6, 8);
    gfx.fillRect(68, 10, 6, 8);

    // Rear light glow
    gfx.fillStyle(0xFF6600, 0.4);
    gfx.fillCircle(9, 14, 6);
    gfx.fillCircle(71, 14, 6);

    // Wheels (rear visible from behind)
    gfx.fillStyle(0x222222);
    gfx.fillEllipse(14, 38, 16, 12);
    gfx.fillEllipse(66, 38, 16, 12);

    // Wheel rims
    gfx.fillStyle(0x888888);
    gfx.fillCircle(14, 38, 3);
    gfx.fillCircle(66, 38, 3);

    // License plate
    gfx.fillStyle(0xFFFFFF);
    gfx.fillRect(32, 24, 16, 8);
    gfx.lineStyle(1, 0x333333);
    gfx.strokeRect(32, 24, 16, 8);

    // Body highlight stripe
    gfx.fillStyle(0xFFFFFF, 0.15);
    gfx.fillRect(8, 8, 64, 3);

    gfx.generateTexture('car_rear', W, H);
    gfx.destroy();
  }

  static _createBarrierTexture(scene) {
    const W = 52, H = 56;
    const gfx = scene.make.graphics({ add: false });

    // Support legs
    gfx.fillStyle(0x666666);
    gfx.fillRect(4, 42, 8, 14);
    gfx.fillRect(40, 42, 8, 14);

    // Main panel
    gfx.fillStyle(0xFF6600);
    gfx.fillRect(2, 4, 48, 40);

    // Warning diagonal stripes
    gfx.fillStyle(0xFFFFFF);
    for (let i = -2; i < 8; i++) {
      const x1 = i * 10;
      gfx.beginPath();
      gfx.moveTo(Math.max(2, x1), 4);
      gfx.lineTo(Math.min(50, x1 + 20), 4);
      gfx.lineTo(Math.min(50, x1 + 12), 44);
      gfx.lineTo(Math.max(2, x1 - 8), 44);
      gfx.closePath();
      gfx.fillPath();
      // Skip one stripe width for alternation
      i++;
    }

    // Border
    gfx.lineStyle(2, 0xCC4400);
    gfx.strokeRect(2, 4, 48, 40);

    // Reflectors
    gfx.fillStyle(0xFFFF00, 0.8);
    gfx.fillCircle(10, 24, 4);
    gfx.fillCircle(42, 24, 4);

    gfx.generateTexture('barrier', W, H);
    gfx.destroy();
  }

  static _createTrashcanTexture(scene) {
    const W = 36, H = 44;
    const gfx = scene.make.graphics({ add: false });

    // Body
    gfx.fillStyle(0x228844);
    gfx.fillRoundedRect(4, 10, 28, 30, 2);

    // Body darker sides (shading)
    gfx.fillStyle(0x1A6636);
    gfx.fillRect(4, 10, 5, 30);
    gfx.fillRect(27, 10, 5, 30);

    // Vertical grooves
    gfx.lineStyle(1, 0x1A6636, 0.5);
    gfx.lineBetween(14, 12, 14, 38);
    gfx.lineBetween(22, 12, 22, 38);

    // Lid (wider than body)
    gfx.fillStyle(0x2AA855);
    gfx.fillRoundedRect(2, 4, 32, 8, 2);

    // Lid handle
    gfx.fillStyle(0x666666);
    gfx.fillRect(14, 0, 8, 6);
    gfx.fillRoundedRect(12, 0, 12, 4, 2);

    // Bottom rim
    gfx.fillStyle(0x1A6636);
    gfx.fillRect(3, 38, 30, 3);

    // Outline
    gfx.lineStyle(1, 0x115522, 0.6);
    gfx.strokeRoundedRect(4, 10, 28, 30, 2);

    gfx.generateTexture('trashcan', W, H);
    gfx.destroy();
  }

  static _createSinkholeTexture(scene) {
    const W = 100, H = 24;
    const gfx = scene.make.graphics({ add: false });

    // Outer crack ring
    gfx.fillStyle(0x333333);
    gfx.fillEllipse(W / 2, H / 2, W, H);

    // Inner dark hole
    gfx.fillStyle(0x080808);
    gfx.fillEllipse(W / 2, H / 2, W * 0.8, H * 0.75);

    // Deepest center
    gfx.fillStyle(0x000000);
    gfx.fillEllipse(W / 2, H / 2 + 1, W * 0.5, H * 0.4);

    // Crack lines radiating outward
    gfx.lineStyle(1, 0x444444, 0.7);
    const angles = [0, 0.7, 1.4, 2.1, 2.8, 3.5, 4.2, 5.0, 5.7];
    for (const a of angles) {
      const innerR = W * 0.25;
      const outerR = W * 0.48;
      gfx.lineBetween(
        W / 2 + Math.cos(a) * innerR, H / 2 + Math.sin(a) * innerR * 0.4,
        W / 2 + Math.cos(a) * outerR, H / 2 + Math.sin(a) * outerR * 0.4
      );
    }

    // Highlight edge (broken pavement look)
    gfx.lineStyle(1, 0x555555, 0.5);
    gfx.strokeEllipse(W / 2, H / 2, W * 0.95, H * 0.9);

    gfx.generateTexture('sinkhole', W, H);
    gfx.destroy();
  }

  // ───────── Collectibles ─────────

  static _createCollectibleTextures(scene) {
    // Coin rotation frames (4 frames)
    const S = 28;
    for (let i = 0; i < 4; i++) {
      const gfx = scene.make.graphics({ add: false });
      const cx = S / 2, cy = S / 2;
      const r = 11;

      // Rotation simulation: vary width
      const widthRatio = [1.0, 0.7, 0.3, 0.7][i];

      // Shadow/glow
      gfx.fillStyle(0xFFDD00, 0.3);
      gfx.fillEllipse(cx, cy, r * 2.4 * widthRatio, r * 2.4);

      // Coin body
      gfx.fillStyle(0xFFDD00);
      gfx.fillEllipse(cx, cy, r * 2 * widthRatio, r * 2);

      // Inner ring
      gfx.lineStyle(1, 0xDDBB00);
      gfx.strokeEllipse(cx, cy, r * 1.5 * widthRatio, r * 1.5);

      if (widthRatio > 0.5) {
        // W symbol (Won currency)
        gfx.fillStyle(0xBB9900);
        gfx.fillRect(cx - 4 * widthRatio, cy - 4, 2 * widthRatio, 8);
        gfx.fillRect(cx + 2 * widthRatio, cy - 4, 2 * widthRatio, 8);
        gfx.fillRect(cx - 5 * widthRatio, cy - 1, 10 * widthRatio, 2);
        gfx.fillRect(cx - 5 * widthRatio, cy + 2, 10 * widthRatio, 2);
      }

      // Shine highlight
      gfx.fillStyle(0xFFFFFF, 0.5);
      gfx.fillEllipse(cx - 3 * widthRatio, cy - 3, 4 * widthRatio, 4);

      gfx.generateTexture(`coin_${i + 1}`, S, S);
      gfx.destroy();
    }

    // Food — Tteokbokki
    TextureFactory._createFoodTexture(scene);
  }

  static _createFoodTexture(scene) {
    const S = 28;
    const gfx = scene.make.graphics({ add: false });
    const cx = S / 2, cy = S / 2;

    // Bowl/container
    gfx.fillStyle(0xFF8844, 0.3);
    gfx.fillCircle(cx, cy, 13);

    // Red sauce base
    gfx.fillStyle(0xCC3300);
    gfx.fillEllipse(cx, cy + 1, 18, 16);

    // Tteok pieces (rice cake sticks)
    gfx.fillStyle(0xFFEECC);
    gfx.fillRoundedRect(5, 8, 6, 14, 2);
    gfx.fillRoundedRect(12, 6, 6, 16, 2);
    gfx.fillRoundedRect(19, 9, 6, 12, 2);

    // Sauce coating on tteok
    gfx.fillStyle(0xDD4400, 0.5);
    gfx.fillRect(6, 14, 4, 4);
    gfx.fillRect(13, 12, 4, 4);
    gfx.fillRect(20, 14, 4, 3);

    // Green onion garnish
    gfx.fillStyle(0x44AA44);
    gfx.fillCircle(8, 20, 2);
    gfx.fillCircle(18, 18, 2);

    // Shine
    gfx.fillStyle(0xFFFFFF, 0.4);
    gfx.fillEllipse(cx - 2, cy - 3, 5, 3);

    gfx.generateTexture('food_tteokbokki', S, S);
    gfx.destroy();
  }

  // ───────── Particles ─────────

  static _createParticleTextures(scene) {
    // Spark (for coin collection)
    let gfx = scene.make.graphics({ add: false });
    gfx.fillStyle(0xFFEE44);
    gfx.fillCircle(4, 4, 4);
    gfx.fillStyle(0xFFFFFF, 0.8);
    gfx.fillCircle(4, 4, 2);
    gfx.generateTexture('particle_spark', 8, 8);
    gfx.destroy();

    // Dust (for running trail)
    gfx = scene.make.graphics({ add: false });
    gfx.fillStyle(0xAAAAAA, 0.6);
    gfx.fillCircle(3, 3, 3);
    gfx.generateTexture('particle_dust', 6, 6);
    gfx.destroy();

    // Hit flash (red circle for impact)
    gfx = scene.make.graphics({ add: false });
    gfx.fillStyle(0xFF0000, 0.5);
    gfx.fillCircle(8, 8, 8);
    gfx.generateTexture('particle_hit', 16, 16);
    gfx.destroy();
  }
}

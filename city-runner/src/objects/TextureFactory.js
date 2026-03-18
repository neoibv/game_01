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

  // ───────── Player — Running Man rear view (48×64) ─────────

  static _createPlayerTextures(scene) {
    const W = 48, H = 64;

    // Run frame 1: left arm forward, right leg forward
    TextureFactory._drawRunningMan(scene, 'player_run_1', W, H, { frame: 0 });
    // Run frame 2: right arm forward, left leg forward
    TextureFactory._drawRunningMan(scene, 'player_run_2', W, H, { frame: 1 });
    // Jump
    TextureFactory._drawRunningMan(scene, 'player_jump', W, H, { jumping: true });
    // Hit (red flash)
    TextureFactory._drawRunningMan(scene, 'player_hit', W, H, { hit: true });
  }

  static _drawRunningMan(scene, key, W, H, opts) {
    const gfx = scene.make.graphics({ add: false });
    const cx = W / 2;

    // Color palette
    const HAIR = opts.hit ? 0x882222 : 0x3B2517;
    const SKIN = opts.hit ? 0xDD6666 : 0xE8B87A;
    const SHIRT = opts.hit ? 0xCC2222 : 0x2266CC;
    const SHIRT_DARK = opts.hit ? 0xAA1111 : 0x1A4E99;
    const PANTS = opts.hit ? 0x661111 : 0x222233;
    const PANTS_DARK = opts.hit ? 0x550E0E : 0x1A1A28;
    const SHOE = opts.hit ? 0xCC8888 : 0xEEEEEE;

    // --- Shadow on ground ---
    if (!opts.jumping) {
      gfx.fillStyle(0x000000, 0.15);
      gfx.fillEllipse(cx, H - 1, 28, 5);
    }

    // === LEGS ===
    if (opts.jumping) {
      // Legs tucked together
      gfx.fillStyle(PANTS);
      gfx.fillRoundedRect(14, 44, 9, 14, 2);
      gfx.fillRoundedRect(25, 44, 9, 14, 2);
      // Shoes
      gfx.fillStyle(SHOE);
      gfx.fillRoundedRect(13, 56, 11, 5, 2);
      gfx.fillRoundedRect(24, 56, 11, 5, 2);
    } else if (opts.frame === 0) {
      // Left leg back (shorter), right leg forward (longer)
      gfx.fillStyle(PANTS_DARK);
      gfx.fillRoundedRect(15, 42, 9, 12, 2); // left leg (back)
      gfx.fillStyle(PANTS);
      gfx.fillRoundedRect(25, 42, 9, 16, 2); // right leg (forward)
      // Shoes
      gfx.fillStyle(SHOE);
      gfx.fillRoundedRect(14, 52, 11, 5, 2); // left shoe
      gfx.fillRoundedRect(24, 56, 11, 5, 2); // right shoe (lower)
    } else {
      // Right leg back (shorter), left leg forward (longer)
      gfx.fillStyle(PANTS);
      gfx.fillRoundedRect(15, 42, 9, 16, 2); // left leg (forward)
      gfx.fillStyle(PANTS_DARK);
      gfx.fillRoundedRect(25, 42, 9, 12, 2); // right leg (back)
      // Shoes
      gfx.fillStyle(SHOE);
      gfx.fillRoundedRect(14, 56, 11, 5, 2); // left shoe (lower)
      gfx.fillRoundedRect(24, 52, 11, 5, 2); // right shoe
    }

    // === TORSO (T-shirt, rear view) ===
    gfx.fillStyle(SHIRT);
    gfx.fillRoundedRect(10, 18, 28, 24, 3);

    // Back center line (shirt fold)
    gfx.lineStyle(1, SHIRT_DARK, 0.4);
    gfx.lineBetween(cx, 22, cx, 40);

    // Shoulder seams
    gfx.lineStyle(1, SHIRT_DARK, 0.3);
    gfx.lineBetween(12, 20, 18, 18);
    gfx.lineBetween(36, 20, 30, 18);

    // === ARMS ===
    if (opts.jumping) {
      // Arms raised up
      gfx.fillStyle(SHIRT);
      gfx.fillRoundedRect(4, 10, 8, 16, 2);  // left arm up
      gfx.fillRoundedRect(36, 10, 8, 16, 2);  // right arm up
      // Hands (skin)
      gfx.fillStyle(SKIN);
      gfx.fillRoundedRect(5, 8, 6, 5, 2);
      gfx.fillRoundedRect(37, 8, 6, 5, 2);
    } else if (opts.frame === 0) {
      // Left arm forward (lower), right arm back (higher)
      gfx.fillStyle(SHIRT_DARK);
      gfx.fillRoundedRect(4, 20, 8, 14, 2);  // left arm (forward)
      gfx.fillStyle(SHIRT);
      gfx.fillRoundedRect(36, 22, 8, 10, 2);  // right arm (back)
      // Hands
      gfx.fillStyle(SKIN);
      gfx.fillRoundedRect(5, 32, 6, 5, 2);
      gfx.fillRoundedRect(37, 30, 6, 5, 2);
    } else {
      // Right arm forward (lower), left arm back (higher)
      gfx.fillStyle(SHIRT);
      gfx.fillRoundedRect(4, 22, 8, 10, 2);  // left arm (back)
      gfx.fillStyle(SHIRT_DARK);
      gfx.fillRoundedRect(36, 20, 8, 14, 2);  // right arm (forward)
      // Hands
      gfx.fillStyle(SKIN);
      gfx.fillRoundedRect(5, 30, 6, 5, 2);
      gfx.fillRoundedRect(37, 32, 6, 5, 2);
    }

    // === NECK (skin) ===
    gfx.fillStyle(SKIN);
    gfx.fillRect(19, 14, 10, 6);

    // === HEAD (back of head) ===
    gfx.fillStyle(HAIR);
    gfx.fillRoundedRect(13, 0, 22, 17, 5);

    // Hair texture (darker top)
    gfx.fillStyle(0x2A1A0F, 0.4);
    gfx.fillRoundedRect(14, 0, 20, 8, 4);

    // Hair side detail
    gfx.fillStyle(HAIR);
    gfx.fillRect(12, 5, 3, 8);  // left sideburn
    gfx.fillRect(33, 5, 3, 8);  // right sideburn

    // Ear hints (skin color peeking out)
    gfx.fillStyle(SKIN, 0.6);
    gfx.fillRoundedRect(11, 7, 4, 5, 2);
    gfx.fillRoundedRect(33, 7, 4, 5, 2);

    // === Subtle outline ===
    gfx.lineStyle(1, 0x000000, 0.15);
    gfx.strokeRoundedRect(10, 18, 28, 24, 3);

    gfx.generateTexture(key, W, H);
    gfx.destroy();
  }

  // ───────── Obstacles ─────────

  static _createObstacleTextures(scene) {
    TextureFactory._createOncomingCarTexture(scene);
    TextureFactory._createZombieTexture(scene);
    TextureFactory._createZombieCrawlerTexture(scene);
    TextureFactory._createSinkholeTexture(scene);
  }

  // Oncoming car — front view (100×52)
  static _createOncomingCarTexture(scene) {
    const W = 100, H = 52;
    const gfx = scene.make.graphics({ add: false });

    // --- Car body (main) ---
    gfx.fillStyle(0xCC3333);
    gfx.fillRoundedRect(6, 10, 88, 30, 5);

    // Hood (top, darker)
    gfx.fillStyle(0xAA2222);
    gfx.fillRoundedRect(12, 2, 76, 14, 4);

    // Windshield (front)
    gfx.fillStyle(0x88CCEE, 0.7);
    gfx.fillRoundedRect(22, 3, 56, 14, 4);

    // Windshield frame
    gfx.lineStyle(1, 0x333333, 0.7);
    gfx.strokeRoundedRect(22, 3, 56, 14, 4);

    // Windshield reflection
    gfx.fillStyle(0xFFFFFF, 0.2);
    gfx.fillRoundedRect(28, 6, 24, 7, 3);

    // Underbody
    gfx.fillStyle(0x881111);
    gfx.fillRect(10, 34, 80, 8);

    // --- Headlights (bright white/yellow rectangles) ---
    gfx.fillStyle(0xFFFFEE);
    gfx.fillRoundedRect(6, 14, 14, 10, 2);
    gfx.fillRoundedRect(80, 14, 14, 10, 2);

    // Headlight glow
    gfx.fillStyle(0xFFFF88, 0.35);
    gfx.fillRoundedRect(3, 12, 20, 14, 4);
    gfx.fillRoundedRect(77, 12, 20, 14, 4);

    // Headlight inner (bright spot)
    gfx.fillStyle(0xFFFFFF, 0.8);
    gfx.fillRoundedRect(9, 17, 8, 4, 1);
    gfx.fillRoundedRect(83, 17, 8, 4, 1);

    // --- Grille ---
    gfx.fillStyle(0x222222);
    gfx.fillRoundedRect(24, 24, 52, 12, 3);

    // Grille horizontal slats
    gfx.fillStyle(0x444444);
    for (let i = 0; i < 6; i++) {
      gfx.fillRect(28 + i * 8, 26, 5, 1);
      gfx.fillRect(28 + i * 8, 29, 5, 1);
      gfx.fillRect(28 + i * 8, 32, 5, 1);
    }

    // --- Front bumper ---
    gfx.fillStyle(0x666666);
    gfx.fillRoundedRect(10, 36, 80, 6, 2);

    // License plate
    gfx.fillStyle(0xFFFFFF);
    gfx.fillRoundedRect(36, 32, 28, 9, 2);
    gfx.lineStyle(1, 0x333333, 0.8);
    gfx.strokeRoundedRect(36, 32, 28, 9, 2);
    // Plate text
    gfx.fillStyle(0x222222);
    gfx.fillRect(41, 35, 4, 3);
    gfx.fillRect(48, 35, 4, 3);
    gfx.fillRect(55, 35, 4, 3);

    // --- Wheels (front view = wide flat rectangles, NOT circles) ---
    gfx.fillStyle(0x111111);
    gfx.fillRoundedRect(2, 42, 24, 8, 2);   // left tire
    gfx.fillRoundedRect(74, 42, 24, 8, 2);   // right tire

    // Rim highlight (horizontal line)
    gfx.fillStyle(0xBBBBBB);
    gfx.fillRect(6, 45, 16, 2);   // left rim
    gfx.fillRect(78, 45, 16, 2);  // right rim

    // Body highlight
    gfx.fillStyle(0xFFFFFF, 0.12);
    gfx.fillRect(12, 12, 76, 3);

    // Outline
    gfx.lineStyle(1, 0x000000, 0.3);
    gfx.strokeRoundedRect(6, 10, 88, 30, 5);

    gfx.generateTexture('oncoming_car', W, H);
    gfx.destroy();
  }

  // Zombie — standing (48×56)
  static _createZombieTexture(scene) {
    const W = 48, H = 56;
    const gfx = scene.make.graphics({ add: false });
    const cx = W / 2;

    // --- Blood pool on ground ---
    gfx.fillStyle(0x660000, 0.3);
    gfx.fillEllipse(cx, H - 2, 30, 6);

    // --- Legs (tattered pants) ---
    gfx.fillStyle(0x334433);
    gfx.fillRect(14, 36, 8, 18);
    gfx.fillRect(26, 36, 8, 16);

    // Torn pants edges
    gfx.fillStyle(0x223322);
    gfx.fillRect(14, 50, 8, 4);
    gfx.fillRect(26, 48, 8, 4);

    // Shoes
    gfx.fillStyle(0x222222);
    gfx.fillRect(12, 52, 11, 4);
    gfx.fillRect(25, 50, 11, 4);

    // --- Torso (torn shirt) ---
    gfx.fillStyle(0x556655);
    gfx.fillRect(10, 16, 28, 22);

    // Torn shirt details
    gfx.fillStyle(0x667766);
    gfx.fillRect(12, 18, 10, 8);

    // Blood stains on shirt
    gfx.fillStyle(0x882222, 0.6);
    gfx.fillCircle(20, 28, 4);
    gfx.fillCircle(30, 22, 3);

    // Rib/wound detail
    gfx.fillStyle(0x774444, 0.5);
    gfx.fillRect(26, 26, 8, 3);

    // --- Arms (outstretched, zombie pose) ---
    gfx.fillStyle(0x77AA77);
    // Left arm reaching out
    gfx.fillRect(0, 18, 12, 6);
    gfx.fillRect(0, 16, 4, 4); // hand
    // Right arm reaching out
    gfx.fillRect(36, 20, 12, 6);
    gfx.fillRect(44, 18, 4, 4); // hand

    // Arm decay marks
    gfx.fillStyle(0x558855);
    gfx.fillRect(2, 20, 6, 2);
    gfx.fillRect(40, 22, 6, 2);

    // Green fingers
    gfx.fillStyle(0x88BB88);
    gfx.fillRect(0, 16, 2, 2);
    gfx.fillRect(0, 19, 2, 2);
    gfx.fillRect(46, 18, 2, 2);
    gfx.fillRect(46, 21, 2, 2);

    // --- Head ---
    gfx.fillStyle(0x88BB88); // zombie green skin
    gfx.fillRoundedRect(14, 0, 20, 18, 4);

    // Hair (messy)
    gfx.fillStyle(0x333333);
    gfx.fillRect(14, 0, 20, 5);
    gfx.fillRect(12, 2, 4, 4);
    gfx.fillRect(33, 1, 3, 5);

    // Eyes (hollow, glowing)
    gfx.fillStyle(0x000000);
    gfx.fillRect(17, 7, 5, 5);
    gfx.fillRect(26, 7, 5, 5);

    // Glowing red pupils
    gfx.fillStyle(0xFF2222);
    gfx.fillRect(18, 8, 3, 3);
    gfx.fillRect(27, 8, 3, 3);

    // Mouth (open, scary)
    gfx.fillStyle(0x440000);
    gfx.fillRect(18, 13, 12, 4);

    // Teeth
    gfx.fillStyle(0xCCCCCC);
    gfx.fillRect(19, 13, 2, 2);
    gfx.fillRect(23, 13, 2, 2);
    gfx.fillRect(27, 13, 2, 2);

    // Decay marks on face
    gfx.fillStyle(0x669966);
    gfx.fillRect(15, 10, 3, 2);
    gfx.fillRect(30, 6, 3, 3);

    gfx.generateTexture('zombie', W, H);
    gfx.destroy();
  }

  // Zombie crawler — crawling on ground (44×36)
  static _createZombieCrawlerTexture(scene) {
    const W = 44, H = 36;
    const gfx = scene.make.graphics({ add: false });

    // Blood trail
    gfx.fillStyle(0x660000, 0.25);
    gfx.fillEllipse(22, H - 2, 36, 5);

    // --- Body (prone, crawling) ---
    gfx.fillStyle(0x556655);
    gfx.fillRoundedRect(8, 14, 28, 14, 3);

    // Torn back
    gfx.fillStyle(0x774444, 0.5);
    gfx.fillRect(16, 16, 12, 4);

    // Blood stain
    gfx.fillStyle(0x882222, 0.5);
    gfx.fillCircle(22, 20, 4);

    // --- Legs (dragging behind) ---
    gfx.fillStyle(0x334433);
    gfx.fillRect(30, 18, 12, 5);
    gfx.fillRect(32, 22, 10, 5);

    // Torn/missing shoe
    gfx.fillStyle(0x222222);
    gfx.fillRect(40, 18, 4, 4);

    // --- Arms (reaching forward) ---
    gfx.fillStyle(0x77AA77);
    gfx.fillRect(2, 16, 10, 5);
    gfx.fillRect(4, 22, 8, 5);

    // Hands/claws
    gfx.fillStyle(0x88BB88);
    gfx.fillRect(0, 17, 4, 3);
    gfx.fillRect(2, 23, 4, 3);

    // Fingers
    gfx.fillStyle(0x99CC99);
    gfx.fillRect(0, 17, 2, 1);
    gfx.fillRect(0, 19, 2, 1);
    gfx.fillRect(2, 23, 2, 1);
    gfx.fillRect(2, 25, 2, 1);

    // --- Head (turned sideways) ---
    gfx.fillStyle(0x88BB88);
    gfx.fillRoundedRect(2, 4, 16, 14, 3);

    // Hair
    gfx.fillStyle(0x333333);
    gfx.fillRect(4, 4, 12, 4);

    // Eye (side view, one visible)
    gfx.fillStyle(0x000000);
    gfx.fillRect(4, 9, 4, 4);
    gfx.fillStyle(0xFF2222);
    gfx.fillRect(5, 10, 2, 2);

    // Mouth
    gfx.fillStyle(0x440000);
    gfx.fillRect(2, 14, 8, 3);

    // Teeth
    gfx.fillStyle(0xCCCCCC);
    gfx.fillRect(3, 14, 2, 2);
    gfx.fillRect(7, 14, 2, 2);

    gfx.generateTexture('zombie_crawler', W, H);
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

    // Highlight edge
    gfx.lineStyle(1, 0x555555, 0.5);
    gfx.strokeEllipse(W / 2, H / 2, W * 0.95, H * 0.9);

    gfx.generateTexture('sinkhole', W, H);
    gfx.destroy();
  }

  // ───────── Collectibles ─────────

  static _createCollectibleTextures(scene) {
    const S = 28;
    for (let i = 0; i < 4; i++) {
      const gfx = scene.make.graphics({ add: false });
      const cx = S / 2, cy = S / 2;
      const r = 11;
      const widthRatio = [1.0, 0.7, 0.3, 0.7][i];

      gfx.fillStyle(0xFFDD00, 0.3);
      gfx.fillEllipse(cx, cy, r * 2.4 * widthRatio, r * 2.4);

      gfx.fillStyle(0xFFDD00);
      gfx.fillEllipse(cx, cy, r * 2 * widthRatio, r * 2);

      gfx.lineStyle(1, 0xDDBB00);
      gfx.strokeEllipse(cx, cy, r * 1.5 * widthRatio, r * 1.5);

      if (widthRatio > 0.5) {
        gfx.fillStyle(0xBB9900);
        gfx.fillRect(cx - 4 * widthRatio, cy - 4, 2 * widthRatio, 8);
        gfx.fillRect(cx + 2 * widthRatio, cy - 4, 2 * widthRatio, 8);
        gfx.fillRect(cx - 5 * widthRatio, cy - 1, 10 * widthRatio, 2);
        gfx.fillRect(cx - 5 * widthRatio, cy + 2, 10 * widthRatio, 2);
      }

      gfx.fillStyle(0xFFFFFF, 0.5);
      gfx.fillEllipse(cx - 3 * widthRatio, cy - 3, 4 * widthRatio, 4);

      gfx.generateTexture(`coin_${i + 1}`, S, S);
      gfx.destroy();
    }

    TextureFactory._createFoodTexture(scene);
  }

  static _createFoodTexture(scene) {
    const S = 28;
    const gfx = scene.make.graphics({ add: false });
    const cx = S / 2, cy = S / 2;

    gfx.fillStyle(0xFF8844, 0.3);
    gfx.fillCircle(cx, cy, 13);

    gfx.fillStyle(0xCC3300);
    gfx.fillEllipse(cx, cy + 1, 18, 16);

    gfx.fillStyle(0xFFEECC);
    gfx.fillRoundedRect(5, 8, 6, 14, 2);
    gfx.fillRoundedRect(12, 6, 6, 16, 2);
    gfx.fillRoundedRect(19, 9, 6, 12, 2);

    gfx.fillStyle(0xDD4400, 0.5);
    gfx.fillRect(6, 14, 4, 4);
    gfx.fillRect(13, 12, 4, 4);
    gfx.fillRect(20, 14, 4, 3);

    gfx.fillStyle(0x44AA44);
    gfx.fillCircle(8, 20, 2);
    gfx.fillCircle(18, 18, 2);

    gfx.fillStyle(0xFFFFFF, 0.4);
    gfx.fillEllipse(cx - 2, cy - 3, 5, 3);

    gfx.generateTexture('food_tteokbokki', S, S);
    gfx.destroy();
  }

  // ───────── Particles ─────────

  static _createParticleTextures(scene) {
    let gfx = scene.make.graphics({ add: false });
    gfx.fillStyle(0xFFEE44);
    gfx.fillCircle(4, 4, 4);
    gfx.fillStyle(0xFFFFFF, 0.8);
    gfx.fillCircle(4, 4, 2);
    gfx.generateTexture('particle_spark', 8, 8);
    gfx.destroy();

    gfx = scene.make.graphics({ add: false });
    gfx.fillStyle(0xAAAAAA, 0.6);
    gfx.fillCircle(3, 3, 3);
    gfx.generateTexture('particle_dust', 6, 6);
    gfx.destroy();

    gfx = scene.make.graphics({ add: false });
    gfx.fillStyle(0xFF0000, 0.5);
    gfx.fillCircle(8, 8, 8);
    gfx.generateTexture('particle_hit', 16, 16);
    gfx.destroy();
  }
}

export class MenuScene extends Phaser.Scene {
  constructor() {
    super({ key: 'MenuScene' });
  }

  create() {
    const { width, height } = this.scale;

    // Sky gradient background
    const bg = this.add.graphics();
    bg.fillGradientStyle(0x87CEEB, 0x87CEEB, 0xFDB97D, 0xFDB97D, 1);
    bg.fillRect(0, 0, width, height);

    // Ground strip
    const ground = this.add.graphics();
    ground.fillStyle(0x888888);
    ground.fillRect(0, height - 120, width, 120);
    // Road line
    ground.fillStyle(0xFFDD00);
    ground.fillRect(0, height - 65, width, 8);

    // Decorative buildings (silhouette)
    this._drawBuildings(bg, width, height);

    // Title
    this.add.text(width / 2, height * 0.22, 'CITY RUNNER', {
      fontSize: '72px',
      fontFamily: 'Arial Black, Arial',
      color: '#FFFFFF',
      stroke: '#003399',
      strokeThickness: 8,
      shadow: { offsetX: 4, offsetY: 4, color: '#000033', blur: 8, fill: true }
    }).setOrigin(0.5);

    this.add.text(width / 2, height * 0.36, '서울을 질주하라!', {
      fontSize: '28px',
      fontFamily: 'Arial',
      color: '#FFEE44',
      stroke: '#333300',
      strokeThickness: 4,
    }).setOrigin(0.5);

    // Best score
    const best = localStorage.getItem('cityrunner_best') || 0;
    this.add.text(width / 2, height * 0.48, `최고 기록: ${Number(best).toLocaleString()}`, {
      fontSize: '24px',
      fontFamily: 'Arial',
      color: '#FFFFFF',
      stroke: '#000000',
      strokeThickness: 3,
    }).setOrigin(0.5);

    // Start button
    const btnBg = this.add.graphics();
    btnBg.fillStyle(0xFF4400, 1);
    btnBg.fillRoundedRect(width / 2 - 120, height * 0.58, 240, 60, 12);

    const btnText = this.add.text(width / 2, height * 0.58 + 30, 'START GAME', {
      fontSize: '28px',
      fontFamily: 'Arial Black, Arial',
      color: '#FFFFFF',
      stroke: '#882200',
      strokeThickness: 4,
    }).setOrigin(0.5);

    // Make interactive
    const hitZone = this.add.zone(width / 2, height * 0.58 + 30, 240, 60).setInteractive({ useHandCursor: true });
    hitZone.on('pointerover', () => {
      btnBg.clear();
      btnBg.fillStyle(0xFF6622, 1);
      btnBg.fillRoundedRect(width / 2 - 120, height * 0.58, 240, 60, 12);
    });
    hitZone.on('pointerout', () => {
      btnBg.clear();
      btnBg.fillStyle(0xFF4400, 1);
      btnBg.fillRoundedRect(width / 2 - 120, height * 0.58, 240, 60, 12);
    });
    hitZone.on('pointerdown', () => this._startGame());

    // Controls hint
    this.add.text(width / 2, height * 0.76, '조작: ← → 이동  |  ↑ / Space 점프', {
      fontSize: '18px',
      fontFamily: 'Arial',
      color: '#CCCCCC',
    }).setOrigin(0.5);

    // Keyboard shortcut
    this.input.keyboard.once('keydown-SPACE', () => this._startGame());
    this.input.keyboard.once('keydown-ENTER', () => this._startGame());

    // Blinking prompt
    const pressText = this.add.text(width / 2, height * 0.68, 'Press SPACE or ENTER to start', {
      fontSize: '20px',
      fontFamily: 'Arial',
      color: '#FFFFFF',
    }).setOrigin(0.5);
    this.tweens.add({
      targets: pressText,
      alpha: 0,
      duration: 600,
      yoyo: true,
      repeat: -1,
    });
  }

  _drawBuildings(gfx, width, height) {
    const buildings = [
      { x: 50,  w: 80,  h: 160, color: 0x8899AA },
      { x: 150, w: 60,  h: 220, color: 0x778899 },
      { x: 230, w: 90,  h: 140, color: 0x99AABB },
      { x: 350, w: 70,  h: 200, color: 0x667788 },
      { x: 450, w: 100, h: 180, color: 0x8899AA },
      { x: 580, w: 60,  h: 240, color: 0x778899 },
      { x: 660, w: 80,  h: 160, color: 0x99AABB },
      { x: 770, w: 90,  h: 210, color: 0x667788 },
      { x: 880, w: 70,  h: 175, color: 0x8899AA },
      { x: 970, w: 100, h: 195, color: 0x778899 },
      { x: 1090,w: 80,  h: 155, color: 0x99AABB },
      { x: 1190,w: 90,  h: 220, color: 0x667788 },
    ];
    buildings.forEach(b => {
      gfx.fillStyle(b.color);
      gfx.fillRect(b.x, height - 120 - b.h, b.w, b.h);
    });
  }

  _startGame() {
    this.scene.start('GameScene', { stageId: 1 });
  }
}

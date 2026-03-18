export class StageClearScene extends Phaser.Scene {
  constructor() {
    super({ key: 'StageClearScene' });
  }

  init(data) {
    this.finalScore = data.score || 0;
    this.baseScore = data.baseScore || 0;
    this.timeBonus = data.timeBonus || 0;
    this.lifeBonus = data.lifeBonus || 0;
    this.livesLeft = data.lives || 0;
    this.timeRemaining = data.timeRemaining || 0;
    this.distance = data.distance || 0;
    this.stageId = data.stageId || 1;
  }

  create() {
    const { width, height } = this.scale;

    // Background
    const bg = this.add.graphics();
    bg.fillGradientStyle(0x001133, 0x001133, 0x003366, 0x003366, 1);
    bg.fillRect(0, 0, width, height);

    // Stars
    for (let i = 0; i < 80; i++) {
      const x = Phaser.Math.Between(0, width);
      const y = Phaser.Math.Between(0, height * 0.7);
      const r = Phaser.Math.FloatBetween(1, 3);
      const star = this.add.circle(x, y, r, 0xFFFFFF);
      this.tweens.add({
        targets: star, alpha: 0.2,
        duration: Phaser.Math.Between(600, 1800),
        yoyo: true, repeat: -1,
        delay: Phaser.Math.Between(0, 1000),
      });
    }

    // Panel
    const panelW = 560, panelH = 420;
    const px = width / 2 - panelW / 2;
    const py = height / 2 - panelH / 2;
    const panel = this.add.graphics();
    panel.fillStyle(0x0A1628, 0.95);
    panel.fillRoundedRect(px, py, panelW, panelH, 20);
    panel.lineStyle(3, 0xFFDD00, 1);
    panel.strokeRoundedRect(px, py, panelW, panelH, 20);

    // Title
    const title = this.add.text(width / 2, py + 50, 'STAGE CLEAR!', {
      fontSize: '52px',
      fontFamily: 'Arial Black, Arial',
      color: '#FFEE00',
      stroke: '#885500',
      strokeThickness: 6,
    }).setOrigin(0.5).setAlpha(0);

    this.tweens.add({
      targets: title,
      alpha: 1,
      scaleX: { from: 0.3, to: 1 },
      scaleY: { from: 0.3, to: 1 },
      ease: 'Back.Out',
      duration: 500,
    });

    // Score breakdown
    const lineY = py + 125;
    const lineGap = 34;
    const leftX = width / 2 - 130;
    const rightX = width / 2 + 150;

    this._scoreLine(leftX, rightX, lineY, 'DISTANCE SCORE:', this.baseScore.toLocaleString(), '#AAAAAA', '#FFFFFF');
    this._scoreLine(leftX, rightX, lineY + lineGap, `TIME BONUS (${Math.floor(this.timeRemaining)}s):`, `+${this.timeBonus.toLocaleString()}`, '#AAAAAA', '#44CCFF');
    this._scoreLine(leftX, rightX, lineY + lineGap * 2, `LIFE BONUS (×${this.livesLeft}):`, `+${this.lifeBonus.toLocaleString()}`, '#AAAAAA', '#44FF88');

    // Divider
    const divGfx = this.add.graphics();
    divGfx.lineStyle(2, 0x555577);
    divGfx.lineBetween(px + 40, lineY + lineGap * 3 - 8, px + panelW - 40, lineY + lineGap * 3 - 8);

    this._scoreLine(leftX, rightX, lineY + lineGap * 3 + 6, 'TOTAL SCORE:', this.finalScore.toLocaleString(), '#FFDD44', '#FFEE00', '28px');

    // Best score
    const best = parseInt(localStorage.getItem('cityrunner_best') || '0', 10);
    if (this.finalScore >= best) {
      const newBest = this.add.text(width / 2, lineY + lineGap * 4 + 16, '★ NEW HIGH SCORE! ★', {
        fontSize: '22px', fontFamily: 'Arial', color: '#FFEE00'
      }).setOrigin(0.5);
      this.tweens.add({ targets: newBest, alpha: 0.3, duration: 500, yoyo: true, repeat: -1 });
    }

    // Buttons
    this._makeButton(width / 2 - 110, py + panelH - 48, 'PLAY AGAIN', () => {
      this.scene.start('GameScene', { stageId: this.stageId });
    }, 0x115511, 0x227722);
    this._makeButton(width / 2 + 120, py + panelH - 48, 'MENU', () => {
      this.scene.start('MenuScene');
    }, 0x333355, 0x5555AA);

    this.input.keyboard.once('keydown-SPACE', () => this.scene.start('GameScene', { stageId: this.stageId }));
    this.input.keyboard.once('keydown-ESC', () => this.scene.start('MenuScene'));
  }

  _scoreLine(lx, rx, y, label, value, labelColor, valueColor, fontSize) {
    this.add.text(lx, y, label, {
      fontSize: fontSize || '20px', fontFamily: 'Arial', color: labelColor
    }).setOrigin(0, 0.5);
    this.add.text(rx, y, value, {
      fontSize: fontSize || '22px', fontFamily: 'Arial Black, Arial', color: valueColor
    }).setOrigin(1, 0.5);
  }

  _makeButton(x, y, label, callback, colorNormal, colorHover) {
    const bg = this.add.graphics();
    const bw = 170, bh = 46;
    bg.fillStyle(colorNormal, 1);
    bg.fillRoundedRect(x - bw / 2, y - bh / 2, bw, bh, 10);
    this.add.text(x, y, label, {
      fontSize: '20px', fontFamily: 'Arial Black, Arial', color: '#FFFFFF'
    }).setOrigin(0.5);
    const zone = this.add.zone(x, y, bw, bh).setInteractive({ useHandCursor: true });
    zone.on('pointerover', () => { bg.clear(); bg.fillStyle(colorHover, 1); bg.fillRoundedRect(x - bw / 2, y - bh / 2, bw, bh, 10); });
    zone.on('pointerout',  () => { bg.clear(); bg.fillStyle(colorNormal, 1); bg.fillRoundedRect(x - bw / 2, y - bh / 2, bw, bh, 10); });
    zone.on('pointerdown', callback);
  }
}

export class GameOverScene extends Phaser.Scene {
  constructor() {
    super({ key: 'GameOverScene' });
  }

  init(data) {
    this.finalScore = data.score || 0;
    this.distance = data.distance || 0;
    this.totalDistance = data.totalDistance || 4000;
    this.stageId = data.stageId || 1;
    this.reason = data.reason || 'dead';
  }

  create() {
    const { width, height } = this.scale;

    // Dark overlay
    const bg = this.add.graphics();
    bg.fillStyle(0x000000, 0.85);
    bg.fillRect(0, 0, width, height);

    // Panel
    const panelW = 500, panelH = 380;
    const px = width / 2 - panelW / 2;
    const py = height / 2 - panelH / 2;
    const panel = this.add.graphics();
    panel.fillStyle(0x1A1A2E, 1);
    panel.fillRoundedRect(px, py, panelW, panelH, 16);
    panel.lineStyle(3, 0xFF4444, 1);
    panel.strokeRoundedRect(px, py, panelW, panelH, 16);

    // Title
    this.add.text(width / 2, py + 50, 'GAME OVER', {
      fontSize: '52px',
      fontFamily: 'Arial Black, Arial',
      color: '#FF4444',
      stroke: '#000000',
      strokeThickness: 6,
    }).setOrigin(0.5);

    // Reason
    const reasons = {
      dead: '생명이 모두 소진되었습니다',
      sinkhole: '싱크홀에 빠졌습니다!',
      time: '시간이 초과되었습니다!',
    };
    this.add.text(width / 2, py + 100, reasons[this.reason] || '', {
      fontSize: '20px',
      fontFamily: 'Arial',
      color: '#FF8888',
    }).setOrigin(0.5);

    // Score
    this.add.text(width / 2, py + 150, `SCORE: ${this.finalScore.toLocaleString()}`, {
      fontSize: '30px',
      fontFamily: 'Arial',
      color: '#FFFFFF',
      stroke: '#000000',
      strokeThickness: 3,
    }).setOrigin(0.5);

    // Progress
    const pct = Math.min(100, (this.distance / this.totalDistance * 100)).toFixed(1);
    const km = (this.distance / 400).toFixed(1);
    this.add.text(width / 2, py + 195, `진행: ${pct}% (${km} km)`, {
      fontSize: '20px',
      fontFamily: 'Arial',
      color: '#AAAAAA',
    }).setOrigin(0.5);

    // Best score
    const best = parseInt(localStorage.getItem('cityrunner_best') || '0', 10);
    const isNew = this.finalScore >= best && this.finalScore > 0;
    this.add.text(width / 2, py + 235, isNew ? '★ NEW BEST! ★' : `BEST: ${best.toLocaleString()}`, {
      fontSize: isNew ? '22px' : '18px',
      fontFamily: 'Arial',
      color: isNew ? '#FFEE00' : '#888888',
    }).setOrigin(0.5);

    // Buttons
    this._makeButton(width / 2 - 110, py + 310, 'RETRY', () => {
      this.scene.start('GameScene', { stageId: this.stageId });
    });
    this._makeButton(width / 2 + 110, py + 310, 'MENU', () => {
      this.scene.start('MenuScene');
    });

    this.input.keyboard.once('keydown-SPACE', () => {
      this.scene.start('GameScene', { stageId: this.stageId });
    });
    this.input.keyboard.once('keydown-ESC', () => {
      this.scene.start('MenuScene');
    });
  }

  _makeButton(x, y, label, callback) {
    const bg = this.add.graphics();
    const bw = 160, bh = 46;
    bg.fillStyle(0x333355, 1);
    bg.fillRoundedRect(x - bw / 2, y - bh / 2, bw, bh, 10);
    this.add.text(x, y, label, {
      fontSize: '22px',
      fontFamily: 'Arial Black, Arial',
      color: '#FFFFFF',
    }).setOrigin(0.5);
    const zone = this.add.zone(x, y, bw, bh).setInteractive({ useHandCursor: true });
    zone.on('pointerover', () => { bg.clear(); bg.fillStyle(0x5555AA, 1); bg.fillRoundedRect(x - bw / 2, y - bh / 2, bw, bh, 10); });
    zone.on('pointerout',  () => { bg.clear(); bg.fillStyle(0x333355, 1); bg.fillRoundedRect(x - bw / 2, y - bh / 2, bw, bh, 10); });
    zone.on('pointerdown', callback);
  }
}

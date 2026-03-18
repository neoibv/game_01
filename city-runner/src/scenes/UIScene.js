export class UIScene extends Phaser.Scene {
  constructor() {
    super({ key: 'UIScene' });
  }

  init(data) {
    this.gameScene = data.gameScene;
  }

  create() {
    const { width } = this.scale;

    // --- Lives (top-left) ---
    this.livesText = this.add.text(20, 16, '', {
      fontSize: '28px',
      fontFamily: 'Arial',
      color: '#FF4444',
    });
    this._renderLives(3);

    // --- Timer (top-center) ---
    this.add.text(width / 2, 10, 'TIME', {
      fontSize: '16px',
      fontFamily: 'Arial Black, Arial',
      color: '#AAAAAA',
    }).setOrigin(0.5, 0);

    this.timerText = this.add.text(width / 2, 30, '2:00', {
      fontSize: '36px',
      fontFamily: 'Arial Black, Arial',
      color: '#FFFFFF',
      stroke: '#000000',
      strokeThickness: 4,
    }).setOrigin(0.5, 0);

    // --- Score (top-right) ---
    this.add.text(width - 20, 10, 'SCORE', {
      fontSize: '16px',
      fontFamily: 'Arial Black, Arial',
      color: '#AAAAAA',
    }).setOrigin(1, 0);

    this.scoreText = this.add.text(width - 20, 30, '0', {
      fontSize: '32px',
      fontFamily: 'Arial Black, Arial',
      color: '#FFFFFF',
      stroke: '#000000',
      strokeThickness: 3,
    }).setOrigin(1, 0);

    // --- Distance (below score) ---
    this.add.text(width - 20, 68, 'DIST', {
      fontSize: '14px',
      fontFamily: 'Arial Black, Arial',
      color: '#AAAAAA',
    }).setOrigin(1, 0);

    this.distText = this.add.text(width - 20, 86, '0.0 km', {
      fontSize: '22px',
      fontFamily: 'Arial',
      color: '#FFDD44',
      stroke: '#000000',
      strokeThickness: 2,
    }).setOrigin(1, 0);

    // --- Speed (bottom-right) ---
    this.speedText = this.add.text(width - 20, this.scale.height - 30, '', {
      fontSize: '16px',
      fontFamily: 'Arial',
      color: '#888888',
    }).setOrigin(1, 1);

    // --- Popup text (center) ---
    this.popupText = this.add.text(width / 2, this.scale.height / 2 - 60, '', {
      fontSize: '52px',
      fontFamily: 'Arial Black, Arial',
      color: '#FFEE00',
      stroke: '#000000',
      strokeThickness: 6,
    }).setOrigin(0.5).setAlpha(0);

    // --- Events ---
    this.events.on('update-lives', (lives) => this._renderLives(lives));
    this.events.on('update-score', (score) => this.scoreText.setText(score.toLocaleString()));
    this.events.on('update-distance', (dist) => {
      const km = (dist / 400).toFixed(1); // 400 Z = 1km
      this.distText.setText(`${km} km`);
    });
    this.events.on('update-timer', (seconds) => {
      const m = Math.floor(seconds / 60);
      const s = Math.floor(seconds % 60);
      const str = `${m}:${String(s).padStart(2, '0')}`;
      this.timerText.setText(str);
      // Flash red when low
      this.timerText.setColor(seconds <= 15 ? '#FF4444' : '#FFFFFF');
    });
    this.events.on('checkpoint', () => this._showPopup('CHECKPOINT!\n+15s', '#44FF44'));
    this.events.on('stage-clear', () => this._showPopup('STAGE CLEAR!!', '#FFEE00'));
  }

  update() {
    if (this.gameScene && this.gameScene.scrollSpeed !== undefined) {
      this.speedText.setText(`SPD: ${Math.round(this.gameScene.scrollSpeed)}`);
    }
  }

  _renderLives(lives) {
    this.livesText.setText('❤'.repeat(Math.max(0, lives)));
  }

  _showPopup(msg, color) {
    this.popupText.setText(msg);
    this.popupText.setColor(color || '#FFEE00');
    this.popupText.setAlpha(1).setScale(0.5);
    this.tweens.killTweensOf(this.popupText);
    this.tweens.add({
      targets: this.popupText,
      scaleX: 1, scaleY: 1,
      duration: 300,
      ease: 'Back.Out',
    });
    this.time.delayedCall(2000, () => {
      this.tweens.add({
        targets: this.popupText,
        alpha: 0,
        duration: 400,
      });
    });
  }
}

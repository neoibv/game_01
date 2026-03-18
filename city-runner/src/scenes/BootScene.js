import { TextureFactory } from '../objects/TextureFactory.js';

export class BootScene extends Phaser.Scene {
  constructor() {
    super({ key: 'BootScene' });
  }

  preload() {
    // Create a loading bar
    const width = this.scale.width;
    const height = this.scale.height;

    const progressBox = this.add.graphics();
    const progressBar = this.add.graphics();

    progressBox.fillStyle(0x222222, 0.8);
    progressBox.fillRect(width / 2 - 160, height / 2 - 20, 320, 40);

    this.load.on('progress', (value) => {
      progressBar.clear();
      progressBar.fillStyle(0x2255FF, 1);
      progressBar.fillRect(width / 2 - 156, height / 2 - 16, 312 * value, 32);
    });

    this.load.on('complete', () => {
      progressBar.destroy();
      progressBox.destroy();
    });

    // No external assets needed – all drawn with Graphics API
  }

  create() {
    TextureFactory.createAll(this);
    this.scene.start('MenuScene');
  }
}

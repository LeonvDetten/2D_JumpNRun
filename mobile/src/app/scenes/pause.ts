// Port of PauseScene: overlay with resume, restart, settings, level select, main menu.

import { drawFancy, fancyText, rect, shade, TITLE_GLOW } from "../../ui/draw";
import type { Screen } from "../../ui/screen";
import { MenuButton } from "../../ui/widgets";
import { Scene, type App } from "../app";
import type { GameScene } from "./game";
import { LevelSelectScene } from "./levelselect";
import { MenuScene } from "./menu";
import { SettingsScene } from "./settings";

export class PauseScene extends Scene {
  overlay = true;
  private buttons: MenuButton[];

  constructor(app: App, private readonly game: GameScene) {
    super(app);
    const items: [string, () => void][] = [
      ["Weiter", () => this.resume()],
      ["Neustart", () => {
        this.app.pop();
        this.game.reset();
      }],
      ["Einstellungen", () => this.app.push(new SettingsScene(this.app))],
      ["Levelauswahl", () => this.app.switch(new LevelSelectScene(this.app, this.game.mode, this.game.tab))],
      ["Hauptmenü", () => this.app.switch(new MenuScene(this.app))],
    ];
    this.buttons = items.map(([label, fn]) => this.layer.add(new MenuButton(label, "", rect(0, 0, 0, 0), () => {
      this.app.audio.play("click");
      fn();
    })));
    this.buttons[0].glow = true;
  }

  private resume(): void {
    this.app.controls.reset();
    this.app.pop();
  }

  layout(): void {
    const s = this.app.screen;
    const w = 260;
    const h = 42;
    const gap = 8;
    const top = Math.max(84, (s.uiH - (this.buttons.length * (h + gap) - gap)) / 2 + 30);
    this.buttons.forEach((b, i) => (b.rect = rect(s.uiW / 2 - w / 2, top + i * (h + gap), w, h)));
  }

  keyDown(code: string): void {
    if (code === "Escape" || code === "KeyP") this.resume();
  }

  draw(screen: Screen): void {
    const ctx = screen.ui();
    shade(ctx, screen.uiW, screen.uiH, 160);
    drawFancy(ctx, fancyText("Pause", 44, TITLE_GLOW), screen.uiW / 2, this.buttons[0].rect.y - 74, "midtop");
    this.layer.draw(ctx);
  }
}

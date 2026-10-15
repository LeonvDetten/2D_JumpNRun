// The level editor scene. The touch editor arrives in stage 5; until then a short note.

import { drawFancy, fancyText, glassPanel, HEADER, rect, text } from "../../ui/draw";
import type { Screen } from "../../ui/screen";
import { CYAN, MUTED } from "../../ui/theme";
import { Button } from "../../ui/widgets";
import { Scene, type App } from "../app";
import { MenuScene } from "./menu";

export class EditorScene extends Scene {
  private back: Button;

  constructor(app: App) {
    super(app);
    this.back = this.layer.add(new Button("‹ Zurück", rect(0, 0, 92, 32), () => this.app.switch(new MenuScene(this.app))));
  }

  layout(): void {
    const s = this.app.screen;
    this.back.rect = rect(s.safe.left + 10, 6, 92, 32);
  }

  update(dt: number): void {
    this.app.background.update(dt);
  }

  draw(screen: Screen): void {
    const ctx = screen.ui();
    this.app.background.draw(ctx, screen.uiW, screen.uiH);
    drawFancy(ctx, fancyText("Level-Editor", 24, HEADER), screen.uiW / 2, 1, "midtop");
    const box = rect(screen.uiW / 2 - 200, screen.uiH / 2 - 60, 400, 120);
    glassPanel(ctx, box, 220, CYAN, 14);
    text(ctx, "Der Touch-Editor kommt in Etappe 5.", screen.uiW / 2, box.y + 40, 15, CYAN, true, "midtop");
    text(ctx, "Bauen, Testspielen und „Prüfen“ durch den Bot.", screen.uiW / 2, box.y + 66, 12, MUTED, false, "midtop");
    this.layer.draw(ctx);
  }
}

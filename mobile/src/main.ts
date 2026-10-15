// Entry point: canvas, save game, app shell, loading screen.

import { App } from "./app/app";
import { Progress } from "./app/progress";
import { EditorScene } from "./app/scenes/editor";
import { LoadingScene } from "./app/scenes/loading";
import { requestPersistence } from "./platform/storage";
import { registerServiceWorker } from "./platform/sw";
import { Screen } from "./ui/screen";

async function main(): Promise<void> {
  const canvas = document.getElementById("game") as HTMLCanvasElement;
  const screen = new Screen(canvas);
  const progress = await Progress.load();
  void requestPersistence();
  const app = new App(screen, progress);
  // deep link: ?start=editor opens the level editor right after loading
  const start = new URLSearchParams(location.search).get("start");
  app.start(new LoadingScene(app, start === "editor" ? () => new EditorScene(app) : undefined));
  if (import.meta.env.DEV) (window as unknown as { app: App }).app = app; // for debugging in the browser console
  registerServiceWorker((apply) => {
    // apply right away while loading or in the menu, otherwise the next time the menu opens
    if (app.top.updatePoint || app.top instanceof LoadingScene) apply();
    else app.updateReady = apply;
  });
}

void main();

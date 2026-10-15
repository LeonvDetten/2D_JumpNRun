// Entry point: canvas, save game, app shell, loading screen.

import { App } from "./app/app";
import { Progress } from "./app/progress";
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
  app.start(new LoadingScene(app));
  if (import.meta.env.DEV) (window as unknown as { app: App }).app = app; // for debugging in the browser console
  registerServiceWorker();
}

void main();

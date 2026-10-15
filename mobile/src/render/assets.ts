// Sprite atlas (tools/export_assets.py) and tinted copies for the ghost and the bot.

export interface Sprite {
  img: CanvasImageSource;
  sx: number;
  sy: number;
  sw: number;
  sh: number;
}

export const PLAYER_STATES = ["IDLE", "RUN", "JUMP", "ATTACK"] as const;
export type PlayerState = (typeof PLAYER_STATES)[number];
export const PLAYER_FRAMES = 7;

export type Tint = "none" | "ghost" | "bot";

export class Assets {
  readonly background: HTMLImageElement;
  private readonly atlas: Record<Tint, CanvasImageSource>;
  private readonly frames: Record<string, [number, number, number, number]>;

  private constructor(atlasImg: HTMLImageElement, frames: Record<string, [number, number, number, number]>, bg: HTMLImageElement) {
    this.frames = frames;
    this.background = bg;
    this.atlas = {
      none: atlasImg,
      // same colour multipliers as the desktop (BLEND_RGBA_MULT), the alpha is applied when drawing
      ghost: tinted(atlasImg, [200, 220, 255]),
      bot: tinted(atlasImg, [110, 230, 255]),
    };
  }

  static async load(base = "./assets/"): Promise<Assets> {
    const [img, json, bg] = await Promise.all([
      loadImage(base + "atlas.png"),
      fetch(base + "atlas.json").then((r) => r.json()),
      loadImage(base + "bg.jpg"),
    ]);
    return new Assets(img, json.frames, bg);
  }

  sprite(name: string, tint: Tint = "none"): Sprite {
    const f = this.frames[name];
    if (!f) throw new Error(`no sprite ${name}`);
    return { img: this.atlas[tint], sx: f[0], sy: f[1], sw: f[2], sh: f[3] };
  }

  player(state: PlayerState, index: number, tint: Tint = "none"): Sprite {
    return this.sprite(`player_${state}_${index}`, tint);
  }
}

export function drawSprite(ctx: CanvasRenderingContext2D, s: Sprite, x: number, y: number, w: number, h: number, flip = false): void {
  if (flip) {
    ctx.save();
    ctx.translate(x + w, y);
    ctx.scale(-1, 1);
    ctx.drawImage(s.img, s.sx, s.sy, s.sw, s.sh, 0, 0, w, h);
    ctx.restore();
  } else {
    ctx.drawImage(s.img, s.sx, s.sy, s.sw, s.sh, x, y, w, h);
  }
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error(`could not load ${src}`));
    img.src = src;
  });
}

function tinted(img: HTMLImageElement, rgb: [number, number, number]): HTMLCanvasElement {
  const c = document.createElement("canvas");
  c.width = img.naturalWidth;
  c.height = img.naturalHeight;
  const ctx = c.getContext("2d")!;
  ctx.drawImage(img, 0, 0);
  ctx.globalCompositeOperation = "multiply";
  ctx.fillStyle = `rgb(${rgb[0]},${rgb[1]},${rgb[2]})`;
  ctx.fillRect(0, 0, c.width, c.height);
  ctx.globalCompositeOperation = "destination-in";
  ctx.drawImage(img, 0, 0);
  return c;
}

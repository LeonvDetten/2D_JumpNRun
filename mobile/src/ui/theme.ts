// Colours of the desktop app (jumpnrun/ui/widgets.py, jumpnrun/app/gfx.py) as CSS strings.

export type RGB = readonly [number, number, number];

export const BG: RGB = [16, 18, 28];
export const PANEL: RGB = [28, 32, 46];
export const PANEL_HI: RGB = [44, 50, 72];
export const PANEL_LINE: RGB = [62, 70, 98];
export const TEXT: RGB = [228, 232, 242];
export const MUTED: RGB = [140, 150, 172];
export const ACCENT: RGB = [82, 156, 255];
export const GREEN: RGB = [72, 204, 122];
export const RED: RGB = [238, 84, 84];
export const YELLOW: RGB = [244, 192, 64];
export const GOLD: RGB = [255, 204, 84];
export const GOLD_DARK: RGB = [170, 110, 30];
export const CYAN: RGB = [92, 224, 255];
export const NIGHT: RGB = [8, 10, 24];

export function css(c: RGB, alpha = 1): string {
  return alpha >= 1 ? `rgb(${c[0]},${c[1]},${c[2]})` : `rgba(${c[0]},${c[1]},${c[2]},${alpha})`;
}

export const FONT_FAMILY = `-apple-system, BlinkMacSystemFont, "SF Pro Rounded", "Segoe UI", Roboto, Helvetica, Arial, sans-serif`;

export function font(size: number, bold = false): string {
  return `${bold ? "700" : "400"} ${size}px ${FONT_FAMILY}`;
}

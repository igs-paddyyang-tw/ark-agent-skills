// UI 元件：有素材用圖、沒有就畫佔位圖形（換圖只動素材，不動程式）
import { Container, Graphics, Sprite, Text, type Texture, type TextStyleOptions } from 'pixi.js';

export const FONT = 'system-ui, "Noto Sans TC", "Noto Sans CJK TC", "Microsoft JhengHei", sans-serif';
export const INK = 0x3a2116;
export const txt = (s: string, size = 28, color = 0xeeeeff, extra: TextStyleOptions = {}) =>
  new Text({ text: s, style: { fontFamily: FONT, fontSize: size, fill: color, fontWeight: '800', align: 'center', ...extra } });
/** 有外框的字（壓在圖上也看得清楚） */
export const otxt = (s: string, size = 28, color = 0xffffff, stroke = INK, width = 6) =>
  txt(s, size, color, { stroke: { color: stroke, width, join: 'round' } });

export function box(w: number, h: number, fill: number, r = 16, stroke?: number): Graphics {
  const g = new Graphics().roundRect(0, 0, w, h, r).fill(fill);
  if (stroke !== undefined) g.roundRect(0, 0, w, h, r).stroke({ width: 4, color: stroke });
  return g;
}

export class Button extends Container {
  private bg: Graphics | Sprite;
  readonly caption: Text;
  private _enabled = true;
  constructor(text: string, readonly w: number, readonly h: number, color: number, onTap: () => void, size = 30, tex?: Texture | null) {
    super();
    if (tex) { const s = new Sprite(tex); s.width = w; s.height = h; this.bg = s; } else this.bg = box(w, h, color, Math.min(w, h) / 2);
    this.caption = tex ? otxt(text, size) : txt(text, size, 0x111111);
    this.caption.anchor.set(0.5);
    this.caption.position.set(w / 2, h / 2);
    this.addChild(this.bg, this.caption);
    this.pivot.set(w / 2, h / 2);
    this.eventMode = 'static';
    this.cursor = 'pointer';
    this.on('pointerdown', () => { if (this._enabled) this.scale.set(0.94); });
    this.on('pointerup', () => this.scale.set(1));
    this.on('pointerupoutside', () => this.scale.set(1));
    this.on('pointertap', () => { if (this._enabled) onTap(); });
  }
  set enabled(v: boolean) { this._enabled = v; this.alpha = v ? 1 : 0.5; }
  get enabled() { return this._enabled; }
  setText(s: string) { this.caption.text = s; }
}

export const money = (n: number) => Math.round(n).toLocaleString('en-US');

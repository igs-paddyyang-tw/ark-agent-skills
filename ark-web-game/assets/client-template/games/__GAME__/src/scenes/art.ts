// Art：畫面取圖與音效的唯一入口（別名 → Texture／音效）。沒有素材（測試、載入失敗、背景還沒載到）時回 null，畫面退回佔位圖形
import { Sprite, Texture } from 'pixi.js';
import type { AssetLoader } from '../runtime/assets.js';
import type { AudioManager } from '../runtime/audio.js';

export class Art {
  constructor(readonly loader: AssetLoader | null = null, readonly audio: AudioManager | null = null) {}
  tex(alias: string): Texture | null {
    const t = this.loader?.tex<Texture>(alias);
    return t instanceof Texture ? t : null;
  }
  /** 依別名建 Sprite（給寬高就縮放到該尺寸）；沒有素材回 null */
  sprite(alias: string, w?: number, h?: number): Sprite | null {
    const t = this.tex(alias);
    if (!t) return null;
    const s = new Sprite(t);
    if (w !== undefined) s.width = w;
    if (h !== undefined) s.height = h;
    return s;
  }
  sfx(alias: string, o?: { volume?: number; rate?: number }) { this.audio?.play(alias, o); }
  /** 玩法前確保素材（背景還沒載完時優先載；失敗也繼續，用佔位圖） */
  async ensureFor(aliases: string[]): Promise<void> {
    const L = this.loader;
    if (!L) return;
    const bundles = new Set(aliases.map((a) => L.bundleOf(a)).filter((b): b is string => !!b));
    await Promise.all([...bundles].map((b) => L.ensure(b)));
  }
}
export const NO_ART = new Art();

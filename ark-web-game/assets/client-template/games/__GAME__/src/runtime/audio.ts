// AudioManager：WebAudio 播音效。瀏覽器規定首次使用者手勢後才能出聲 → unlock()；沒有 AudioContext（node、舊瀏覽器）時全部靜默不報錯
import type { SoundEntry } from './assets.js';

type Ctx = AudioContext;
export class AudioManager {
  ctx: Ctx | null = null;
  muted = false;
  master = 0.8;
  readonly buffers = new Map<string, AudioBuffer>();
  readonly volume = new Map<string, number>();
  failed: string[] = [];
  private loading: Promise<void> | null = null;
  constructor(private win: { AudioContext?: typeof AudioContext; webkitAudioContext?: typeof AudioContext; document?: Document } = globalThis as any,
    private fetchBuf: (url: string) => Promise<ArrayBuffer> = (u) => fetch(u).then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.arrayBuffer(); })) {
    const C = win.AudioContext ?? win.webkitAudioContext;
    if (C) { try { this.ctx = new C(); } catch { this.ctx = null; } }
  }

  /** 依瀏覽器支援挑格式：ogg（Vorbis）可播用 ogg，否則 m4a */
  pick(src: string[]): string | undefined {
    const a = this.win.document?.createElement?.('audio');
    const ok = (ext: string) => {
      if (!a) return ext === 'ogg';
      const t = ext === 'ogg' ? 'audio/ogg; codecs="vorbis"' : ext === 'm4a' ? 'audio/mp4; codecs="mp4a.40.2"' : ext === 'mp3' ? 'audio/mpeg' : '';
      return !!t && a.canPlayType(t) !== '';
    };
    return src.find((s) => ok(s.split('.').pop() ?? '')) ?? src[0];
  }

  load(sounds: SoundEntry[], base: string): Promise<void> {
    if (this.loading) return this.loading;
    this.loading = (async () => {
      if (!this.ctx) return;
      await Promise.all(sounds.map(async (s) => {
        const url = this.pick(s.src);
        if (!url) return;
        try {
          const buf = await this.fetchBuf(base + url);
          this.buffers.set(s.alias, await this.ctx!.decodeAudioData(buf));
          this.volume.set(s.alias, s.volume ?? 1);
        } catch (e) { this.failed.push(s.alias); console.warn('[audio] 載入失敗', s.alias, e); }
      }));
    })();
    return this.loading;
  }

  unlock(): void { if (this.ctx && this.ctx.state !== 'running') void this.ctx.resume().catch(() => {}); }

  play(alias: string, o: { volume?: number; rate?: number } = {}): void {
    const c = this.ctx, b = this.buffers.get(alias);
    if (this.muted || !c || !b || c.state !== 'running') return;
    const src = c.createBufferSource();
    src.buffer = b;
    if (o.rate) src.playbackRate.value = o.rate;
    const g = c.createGain();
    g.gain.value = this.master * (this.volume.get(alias) ?? 1) * (o.volume ?? 1);
    src.connect(g).connect(c.destination);
    src.start();
  }
}

// AssetLoader：讀 pgp-assets-manifest/1（wg_pack_assets 產生）→ PixiJS Assets 分包載入
//   必要 bundle 載完才可玩（Boot loading 步驟）；其餘背景載入；玩法前 ensure() 優先載；沒載到的圖回 null（畫面退回佔位）
export interface ManifestBundle { name: string; assets: { alias: string; src: string }[] }
export interface SoundEntry { alias: string; bundle: string; src: string[]; volume?: number }
export interface AssetsManifest { bundles: ManifestBundle[]; sounds: SoundEntry[]; meta: { schema: string; game_key?: string; version?: string; required: string[] } }

/** 與 PixiJS Assets 相容的最小介面（測試可換假的） */
export interface AssetBackend {
  init(o: { manifest: { bundles: ManifestBundle[] }; basePath: string }): Promise<void>;
  loadBundle(name: string, onProgress?: (p: number) => void): Promise<unknown>;
  get(alias: string): unknown;
}

export type BundleState = 'idle' | 'loading' | 'loaded' | 'failed';
export interface AssetMetrics { manifest_fetch_ms?: number; core_bundle_ms?: number; background_done_ms?: number; asset_fail?: number }

export class AssetLoader {
  man: AssetsManifest | null = null;
  base = '';
  readonly state = new Map<string, BundleState>();
  readonly metrics: AssetMetrics = {};
  private pending = new Map<string, Promise<boolean>>();
  constructor(private backend: AssetBackend, private fetchJson: (url: string) => Promise<unknown> = (u) => fetch(u).then((r) => { if (!r.ok) throw Object.assign(new Error(`HTTP ${r.status}`), { code: 'ASSET_MANIFEST_FAILED' }); return r.json(); }), private now: () => number = () => performance.now()) {}

  /** 讀 manifest 並初始化（manifestUrl 所在資料夾 = 素材根） */
  async open(manifestUrl: string): Promise<AssetsManifest> {
    const t0 = this.now();
    let m: AssetsManifest;
    try { m = (await this.fetchJson(manifestUrl)) as AssetsManifest; } catch (e: any) { throw Object.assign(new Error(`素材清單讀取失敗：${e?.message ?? e}`), { code: 'ASSET_MANIFEST_FAILED' }); }
    if (m?.meta?.schema !== 'pgp-assets-manifest/1' || !Array.isArray(m.bundles)) throw Object.assign(new Error('素材清單格式不符'), { code: 'ASSET_MANIFEST_FAILED' });
    this.man = m;
    this.base = manifestUrl.slice(0, manifestUrl.lastIndexOf('/') + 1);
    for (const b of m.bundles) this.state.set(b.name, 'idle');
    await this.backend.init({ manifest: { bundles: m.bundles }, basePath: this.base });
    this.metrics.manifest_fetch_ms = Math.round(this.now() - t0);
    return m;
  }

  get required(): string[] { return (this.man?.meta.required ?? []).filter((b) => this.state.has(b)); }
  get optional(): string[] { return (this.man?.bundles ?? []).map((b) => b.name).filter((n) => !this.required.includes(n)); }

  /** 載一個 bundle（同一個只載一次）；回傳是否成功 */
  ensure(name: string, onProgress?: (p: number) => void): Promise<boolean> {
    if (!this.state.has(name)) return Promise.resolve(true);        // 沒有圖的 bundle（例：只有音效）
    const hit = this.pending.get(name);
    if (hit) return hit;
    this.state.set(name, 'loading');
    const p = this.backend.loadBundle(name, onProgress).then(() => { this.state.set(name, 'loaded'); return true; }, (e) => {
      this.state.set(name, 'failed');
      this.metrics.asset_fail = (this.metrics.asset_fail ?? 0) + 1;
      console.warn('[assets] bundle 載入失敗', name, e);
      return false;
    });
    this.pending.set(name, p);
    return p;
  }

  /** 必要 bundle：全部載完才回；任一失敗 → 丟 ASSET_LOAD_FAILED（Boot 進 error） */
  async loadRequired(onProgress?: (p: number) => void): Promise<void> {
    const t0 = this.now();
    const req = this.required;
    let done = 0;
    for (const b of req) {
      const ok = await this.ensure(b, (p) => onProgress?.((done + p) / req.length));
      if (!ok) throw Object.assign(new Error(`必要素材 ${b} 載入失敗`), { code: 'ASSET_LOAD_FAILED' });
      done++;
    }
    this.metrics.core_bundle_ms = Math.round(this.now() - t0);
  }

  /** 進場後背景載入其餘 bundle（依序、不擋遊戲） */
  async background(): Promise<void> {
    const t0 = this.now();
    for (const b of this.optional) await this.ensure(b);
    this.metrics.background_done_ms = Math.round(this.now() - t0);
  }

  tex<T = unknown>(alias: string): T | null {
    try { return (this.backend.get(alias) as T) ?? null; } catch { return null; }
  }
  bundleOf(alias: string): string | undefined { return this.man?.bundles.find((b) => b.assets.some((a) => a.alias === alias))?.name; }
}

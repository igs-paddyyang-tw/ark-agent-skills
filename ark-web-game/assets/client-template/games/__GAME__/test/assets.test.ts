import { describe, expect, it } from 'vitest';
import { AssetLoader, type AssetBackend } from '../src/runtime/assets.js';
import { AudioManager } from '../src/runtime/audio.js';
import { Art } from '../src/scenes/art.js';

const MAN = {
  bundles: [{ name: 'core', assets: [{ alias: 'sym_A', src: 'core/sym_A.1.webp' }] }, { name: 'feat', assets: [{ alias: 'frame_ST', src: 'feat/f.webp' }] }, { name: 'more', assets: [{ alias: 'x', src: 'more/x.webp' }] }],
  sounds: [{ alias: 'sfx_stop', bundle: 'audio', src: ['audio/s.ogg', 'audio/s.m4a'] }],
  meta: { schema: 'pgp-assets-manifest/1', required: ['core'] },
};
function fake(fail: string[] = []) {
  const log: string[] = [];
  const store = new Map<string, unknown>();
  const be: AssetBackend = {
    init: async (o) => { log.push(`init ${o.basePath} ${o.manifest.bundles.length}`); },
    loadBundle: async (n) => { log.push(`load ${n}`); if (fail.includes(n)) throw new Error('404'); for (const b of MAN.bundles) if (b.name === n) for (const a of b.assets) store.set(a.alias, { tex: a.alias }); },
    get: (a) => store.get(a),
  };
  return { be, log };
}

describe('AssetLoader', () => {
  it('必要 bundle 先載、其餘背景依序；同一 bundle 只載一次；別名找 bundle', async () => {
    const { be, log } = fake();
    const L = new AssetLoader(be, async () => MAN);
    await L.open('http://h/g/assets/manifest.json');
    expect(L.base).toBe('http://h/g/assets/');
    expect(L.required).toEqual(['core']);
    await L.loadRequired();
    expect(L.tex('sym_A')).toEqual({ tex: 'sym_A' });
    expect(L.tex('frame_ST')).toBeNull();
    await Promise.all([L.ensure('feat'), L.ensure('feat'), L.background()]);
    expect(log).toEqual(['init http://h/g/assets/ 3', 'load core', 'load feat', 'load more']);
    expect(L.bundleOf('frame_ST')).toBe('feat');
    expect(L.state.get('more')).toBe('loaded');
    expect(L.metrics.core_bundle_ms).toBeGreaterThanOrEqual(0);
  });
  it('必要 bundle 失敗 → ASSET_LOAD_FAILED；非必要失敗只記數不擋', async () => {
    const a = new AssetLoader(fake(['core']).be, async () => MAN);
    await a.open('/assets/manifest.json');
    await expect(a.loadRequired()).rejects.toMatchObject({ code: 'ASSET_LOAD_FAILED' });
    const b = new AssetLoader(fake(['more']).be, async () => MAN);
    await b.open('/assets/manifest.json');
    await b.loadRequired();
    const warn = console.warn; console.warn = () => {};
    await b.background();
    console.warn = warn;
    expect(b.state.get('more')).toBe('failed');
    expect(b.metrics.asset_fail).toBe(1);
  });
  it('清單讀不到或格式不符 → ASSET_MANIFEST_FAILED', async () => {
    await expect(new AssetLoader(fake().be, async () => { throw new Error('HTTP 404'); }).open('/m.json')).rejects.toMatchObject({ code: 'ASSET_MANIFEST_FAILED' });
    await expect(new AssetLoader(fake().be, async () => ({ bundles: [] })).open('/m.json')).rejects.toMatchObject({ code: 'ASSET_MANIFEST_FAILED' });
  });
});

describe('AudioManager／Art', () => {
  it('沒有 AudioContext（node）→ 靜默不報錯', async () => {
    const a = new AudioManager({});
    await a.load(MAN.sounds as any, '/');
    a.unlock();
    expect(() => a.play('sfx_stop')).not.toThrow();
    expect(a.ctx).toBeNull();
  });
  it('依瀏覽器支援挑格式：不支援 ogg → m4a', () => {
    const doc = { createElement: () => ({ canPlayType: (t: string) => (t.startsWith('audio/mp4') ? 'probably' : '') }) } as any;
    expect(new AudioManager({ document: doc }).pick(['a.ogg', 'a.m4a'])).toBe('a.m4a');
    const doc2 = { createElement: () => ({ canPlayType: () => 'maybe' }) } as any;
    expect(new AudioManager({ document: doc2 }).pick(['a.ogg', 'a.m4a'])).toBe('a.ogg');
  });
  it('Art：沒有素材時 tex／sprite 回 null（畫面用佔位）', async () => {
    const art = new Art();
    expect(art.tex('sym_A')).toBeNull();
    expect(art.sprite('logo')).toBeNull();
    await expect(art.ensureFor(['frame_ST'])).resolves.toBeUndefined();
  });
});

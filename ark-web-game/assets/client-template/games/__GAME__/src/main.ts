// 進入點：網址參數決定結果來源 → Boot（連線 → 載入 → 建畫面 → 可玩）→ 視窗掛勾（e2e／除錯）
//   ?service=ws&url=ws://host/ws&arkId=…&token=…&dev   （預設 ws 連同站 /ws）
//   ?service=http&base=…&gameId=huff
//   ?service=replay&trace=<trace.json 網址>
//   ?speed=20（演出加速）  ?proto_result=…（測試協定不相容）  ?assets=<manifest 網址>｜none（佔位模式）  ?mute
//   素材：Boot 載入步驟讀 manifest、載完必要 bundle 才可玩；其餘 bundle 與音效在可玩後背景載入
import { Application, Assets } from 'pixi.js';
import { createService, Recorder, ReplayService, serviceFromQuery, WsService, type GameService } from '@pgp/game-service';
import { PROTOCOL, ServiceError, type SpinResult } from '@pgp/shared-types';
import { GAME } from './game.config.js';
import { GameController } from './game/controller.js';
import type { PresentEvent } from './game/present-events.js';
import { AssetLoader } from './runtime/assets.js';
import { AudioManager } from './runtime/audio.js';
import { Boot } from './runtime/boot.js';
import { RealClock } from './runtime/clock.js';
import { Tweener } from './runtime/tween.js';
import { Art } from './scenes/art.js';
import { MainScene } from './scenes/main.js';

const q = new URLSearchParams(location.search);
const telemetry: { name: string; data: Record<string, unknown> }[] = [];
const boot = new Boot(() => performance.now(), (name, data) => { telemetry.push({ name, data }); console.info('[telemetry]', name, data); });
const bootEl = document.getElementById('boot')!;
boot.events.on('state', ({ state, error }) => {
  bootEl.dataset.state = state;
  bootEl.textContent = state === 'error' ? `無法開始遊戲（${error?.code}）：${error?.message}` : state === 'playable' ? '' : '載入中…';
});

const clock = new RealClock();
clock.speed = Number(q.get('speed') ?? 1) || 1;
const tw = new Tweener(clock);
const presentLog: PresentEvent[] = [];
let service: Recorder;
let ctrl: GameController | null = null;
let scene: MainScene | null = null;
let info: any = null;
const assetUrl = q.get('assets') ?? GAME.assets;
const loader = assetUrl === 'none' ? null : new AssetLoader(Assets as any);
const audio = new AudioManager();
audio.muted = q.has('mute');
const art = new Art(loader, audio);
const unlock = () => audio.unlock();
window.addEventListener('pointerdown', unlock, { capture: true });
window.addEventListener('keydown', unlock, { capture: true });

/** 沒給 arkId 時，每個瀏覽器固定一個訪客代號（存 localStorage；讀不到就每次新產）。同代號兩條連線會互踢（ark-go KickSameID），所以不能大家共用 'anon' */
function guestId(): string {
  const make = () => `guest-${Math.random().toString(36).slice(2, 10)}`;
  try {
    const k = `pgp:${GAME.key}:arkId`;
    const v = localStorage.getItem(k) || make();
    localStorage.setItem(k, v);
    return v;
  } catch { return make(); }
}

async function makeService(): Promise<GameService> {
  if (q.get('service') === 'replay') {
    const url = q.get('trace');
    if (!url) throw new ServiceError('BAD_REQUEST', '重播需要 ?trace=<網址>');
    return new ReplayService(await (await fetch(url)).json());
  }
  const cfg = serviceFromQuery(q, location, { gameId: GAME.key }) ?? { kind: 'ws' as const, url: `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`, arkId: q.get('arkId') ?? undefined, token: q.get('token') ?? undefined, dev: q.has('dev') };
  if (cfg.kind === 'ws') {
    if (!cfg.arkId) cfg.arkId = guestId();
    const proto = { ...PROTOCOL, ...(q.get('proto_result') ? { result: q.get('proto_result')! } : {}) };
    return new WsService({ ...cfg, protocol: proto, onSlow: (s) => { if (scene && ctrl) { ctrl.hud.message = s ? '連線較慢…' : ''; scene.render(ctrl.hud); } } });
  }
  return createService(cfg);
}

const app = new Application();
void boot.run({
  connect: async () => { service = new Recorder(await makeService()); info = await service.init(); },
  load: async () => {
    await app.init({ resizeTo: window, background: 0x10131c, antialias: true, preference: 'webgl' });
    document.getElementById('app')!.appendChild(app.canvas);
    if (loader) {
      await loader.open(new URL(assetUrl, location.href).href);
      await loader.loadRequired((p) => { bootEl.textContent = `載入中… ${Math.round(p * 100)}%`; });
    }
    await document.fonts?.ready;
  },
  build: async () => {
    scene = new MainScene(app, clock, tw, info?.symbols, art);
    app.stage.addChild(scene);
    ctrl = new GameController(service, scene, clock);
    scene.ctrl = ctrl;
    ctrl.events.on('present', (e) => presentLog.push(e));
    ctrl.events.on('error', (e) => console.warn('[service]', e.code, e.message));
    await ctrl.start(info);
  },
}).then((ok) => {
  if (!ok || !loader) return;
  const t0 = performance.now();
  void Promise.all([loader.background(), audio.load(loader.man?.sounds ?? [], loader.base)]).then(() => {
    const m = { ...loader.metrics, audio_ms: Math.round(performance.now() - t0), audio_failed: audio.failed.length };
    telemetry.push({ name: 'assets', data: m });
    console.info('[telemetry] assets', m);
  });
});

// 視窗掛勾（e2e、除錯；不放 seed 等敏感值）
declare global { interface Window { __pgp: unknown } }
window.__pgp = {
  boot, telemetry, presentLog, clock, loader, audio,
  get info() { return info; },
  get hud() { return ctrl?.hud; },
  get service() { return service; },
  spin: () => ctrl!.spin(),
  play: async (r: SpinResult) => { await ctrl!.play(r); },
  /** dev Server：強制情境 → 播放 → 結算 → ack（與一般局同流程） */
  force: async (scene: unknown) => {
    if (!service.debug) throw new ServiceError('NOT_SUPPORTED', '需要 dev Server（?dev）');
    const h = ctrl!.hud;
    h.busy = true;
    const r = await service.debug.force(scene, { bet: h.bet });
    await ctrl!.play(r);
    h.balance = r.balanceAfter; h.busy = false;
    await service.ack(r.roundId);
    return r;
  },
  trace: () => service.trace(),
  setSpeed: (s: number) => { clock.speed = s; },
};

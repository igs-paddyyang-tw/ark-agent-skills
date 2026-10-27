// Boot 生命週期（ark-web-game references/delivery.md §5）：idle → connecting → loading → core_ready → playable；任一步失敗 → error
//   指標：boot → core_ready（必要素材）→ playable（可按 SPIN）；time_to_playable_ms 回報遙測
import { Emitter } from './events.js';

export type BootState = 'idle' | 'connecting' | 'loading' | 'core_ready' | 'playable' | 'error';
const NEXT: Record<BootState, BootState[]> = {
  idle: ['connecting', 'error'], connecting: ['loading', 'error'], loading: ['core_ready', 'error'],
  core_ready: ['playable', 'error'], playable: [], error: [],
};
export interface BootMetrics { time_to_core_ready_ms?: number; time_to_playable_ms?: number; [k: string]: number | undefined }
export type Telemetry = (name: string, data: Record<string, unknown>) => void;

export class Boot {
  state: BootState = 'idle';
  error: { code: string; message: string } | null = null;
  readonly metrics: BootMetrics = {};
  readonly events = new Emitter<{ state: { state: BootState; error?: Boot['error'] } }>();
  private t0: number;
  constructor(private now: () => number = () => performance.now(), private telemetry: Telemetry = () => {}) { this.t0 = now(); }
  to(s: BootState) {
    if (!NEXT[this.state].includes(s)) throw new Error(`Boot 狀態不能從 ${this.state} 到 ${s}`);
    this.state = s;
    const ms = Math.round(this.now() - this.t0);
    if (s === 'core_ready') this.metrics.time_to_core_ready_ms = ms;
    if (s === 'playable') { this.metrics.time_to_playable_ms = ms; this.telemetry('boot', { ...this.metrics }); }
    this.events.emit('state', { state: s });
  }
  fail(code: string, message: string) {
    if (this.state === 'playable' || this.state === 'error') return;
    this.error = { code, message };
    this.state = 'error';
    this.telemetry('boot_error', { code, at: Math.round(this.now() - this.t0) });
    this.events.emit('state', { state: 'error', error: this.error });
  }
  /** 依序跑各步驟；失敗 → error（錯誤碼取 e.code） */
  async run(steps: { connect: () => Promise<void>; load: () => Promise<void>; build: () => Promise<void> }): Promise<boolean> {
    try {
      this.to('connecting'); await steps.connect();
      this.to('loading'); await steps.load();
      this.to('core_ready'); await steps.build();
      this.to('playable');
      return true;
    } catch (e: any) {
      this.fail(e?.code ?? 'BOOT_FAILED', String(e?.message ?? e));
      return false;
    }
  }
}

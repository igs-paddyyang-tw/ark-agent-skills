// WsService：ark-go WebSocket（sys "slot"）。重試同 requestId、新 sn；ready() 等自動重連不另開連線；分段組回、缺段 fetch 補拿；交給遊戲前驗 SpinResult
import { ArkConn, type ArkConnOptions, type ConnState } from '@pgp/ark-wire';
import { isRetryable, PROTOCOL, ServiceError, validateSpinResult, type Protocol, type SpinResult } from '@pgp/shared-types';
import { newRequestId, type ActionRequest, type GameService, type ServiceInfo, type ServiceStats, type SpinRequest } from './types.js';

export interface WsServiceOptions {
  url: string; arkId?: string; token?: string; timeout?: number; retries?: number; dev?: boolean;
  protocol?: Protocol; WebSocket?: typeof WebSocket; aliveMs?: number; reconnect?: ArkConnOptions['reconnect'];
  onSlow?: (slow: boolean) => void; onState?: (s: ConnState, why?: unknown) => void; backoffMs?: number;
}
type Part = { roundId: string; i: number; n: number; part: string };

export class WsService implements GameService {
  readonly kind = 'ws' as const;
  readonly conn: ArkConn;
  readonly debug: GameService['debug'];
  readonly stats: ServiceStats = { calls: 0, retries: 0, errors: {}, lastMs: 0, chunked: 0, fetched: 0 };
  private parts = new Map<string, Part[]>();
  private o: Required<Pick<WsServiceOptions, 'timeout' | 'retries' | 'backoffMs'>> & WsServiceOptions;

  constructor(opts: WsServiceOptions) {
    this.o = { timeout: 10000, retries: 2, backoffMs: 200, ...opts };
    this.conn = new ArkConn({
      url: opts.url, WebSocket: opts.WebSocket, timeoutMs: this.o.timeout, aliveMs: opts.aliveMs, reconnect: opts.reconnect,
      auth: () => ({ ark_id: String(opts.arkId ?? 'anon'), ark_token: String(opts.token ?? 'dev') }), onState: opts.onState,
    } as ArkConnOptions);
    this.conn.on<Part>('slot', 'result', (d) => {
      if (!d?.roundId) return;
      if (!this.parts.has(d.roundId)) this.parts.set(d.roundId, []);
      this.parts.get(d.roundId)!.push(d);
    });
    this.debug = opts.dev ? { force: (scene, o = {}) => this.spinLike('force', { scene, bet: o.bet, requestId: o.requestId ?? newRequestId() }) } : null;
  }

  private async once(cmd: string, data?: unknown): Promise<any> {
    try { await this.conn.ready(); } catch (e: any) { throw new ServiceError(e.code ?? 'NETWORK', e.message, e.data); }
    const slow = this.o.onSlow ? setTimeout(() => this.o.onSlow!(true), 3000) : undefined;
    const t0 = Date.now();
    try {
      const d: any = await this.conn.request('slot', cmd, data, { timeoutMs: this.o.timeout });
      if (!d || d.status !== 0) {
        const st = d?.status;
        throw new ServiceError(d?.code ?? (st === -999 ? 'SESSION_EXPIRED' : `WS_${st}`), d?.message ?? d?.msg ?? 'WS 錯誤', { status: st });
      }
      return d;
    } catch (e: any) {
      throw e instanceof ServiceError ? e : new ServiceError(e.code ?? 'NETWORK', e.message, e.data);
    } finally {
      if (slow) { clearTimeout(slow); this.o.onSlow!(false); }
      this.stats.lastMs = Date.now() - t0;
    }
  }

  private async req(cmd: string, data?: unknown): Promise<any> {
    this.stats.calls++;
    let last: ServiceError | undefined;
    for (let i = 0; i <= this.o.retries; i++) {
      try { return await this.once(cmd, data); } catch (e) {
        last = e as ServiceError;
        this.stats.errors[last.code] = (this.stats.errors[last.code] ?? 0) + 1;
        if (!isRetryable(last.code) || i === this.o.retries) break;
        this.stats.retries++;
        await new Promise((r) => setTimeout(r, this.o.backoffMs * (i + 1)));
      }
    }
    throw last;
  }

  private async assemble(d: { roundId: string; chunks: number; chars?: number }, depth = 0): Promise<SpinResult> {
    const got = (this.parts.get(d.roundId) ?? []).sort((a, b) => a.i - b.i);
    this.parts.delete(d.roundId);
    const text = got.map((x) => x.part).join('');   // 分段是 \uXXXX 轉義後的 JSON 文字，JSON.parse 自行還原
    if (got.length === d.chunks && (d.chars === undefined || text.length === d.chars)) { this.stats.chunked!++; return JSON.parse(text); }
    if (depth > 0) throw new ServiceError('RESULT_INCOMPLETE', `分段不完整（${got.length}/${d.chunks}）`);
    this.stats.fetched!++;
    const f = await this.req('fetch', { roundId: d.roundId });
    return f.result !== undefined ? f.result : this.assemble(f, depth + 1);
  }

  private async spinLike(cmd: string, data: unknown): Promise<SpinResult> {
    const d = await this.req(cmd, data);
    const r = d.result !== undefined ? d.result : await this.assemble(d);
    const errs = validateSpinResult(r);
    if (errs.length) throw new ServiceError('SCHEMA_INVALID', `SpinResult 不合契約：${errs[0]}`, { errors: errs });
    return r as SpinResult;
  }

  async init(): Promise<ServiceInfo> { return (await this.req('init', { protocol: this.o.protocol ?? PROTOCOL })).info; }
  async balance(): Promise<number> { return (await this.req('balance')).balance; }
  spin(req: SpinRequest) { return this.spinLike('spin', { bet: req.bet, requestId: req.requestId ?? newRequestId() }); }
  action(req: ActionRequest) { return this.spinLike('action', { ...req, requestId: req.requestId ?? newRequestId() }); }
  ack(roundId: string) { return this.req('ack', { roundId }).then(() => true, () => false); }
  fetch(roundId: string) { return this.spinLike('fetch', { roundId }); }
  close() { this.conn.close(); }
}

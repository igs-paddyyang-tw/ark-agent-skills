// HttpService：go-server／slot-bot HTTP（API-101～107：/api/slot/{gameId}/init|balance|spin|action|ack|round/{id}|dev/force）
import { isRetryable, PROTOCOL, ServiceError, validateSpinResult, type SpinResult } from '@pgp/shared-types';
import { newRequestId, type ActionRequest, type GameService, type ServiceInfo, type ServiceStats, type SpinRequest } from './types.js';

export interface HttpServiceOptions { base: string; gameId: string; token?: string; timeout?: number; retries?: number; dev?: boolean; fetch?: typeof fetch; onSlow?: (s: boolean) => void }

export class HttpService implements GameService {
  readonly kind = 'http' as const;
  readonly debug: GameService['debug'];
  readonly stats: ServiceStats = { calls: 0, retries: 0, errors: {}, lastMs: 0 };
  private f: typeof fetch;
  constructor(private o: HttpServiceOptions) {
    this.f = o.fetch ?? globalThis.fetch.bind(globalThis);
    this.debug = o.dev ? { force: (scene, x = {}) => this.result('POST', 'dev/force', { scene, ...x }) } : null;
  }
  url(path: string) { return `${this.o.base.replace(/\/$/, '')}/api/slot/${encodeURIComponent(this.o.gameId)}/${path}`; }
  private async once(method: string, path: string, body?: unknown): Promise<any> {
    const ctl = new AbortController();
    const slow = this.o.onSlow ? setTimeout(() => this.o.onSlow!(true), 3000) : undefined;
    const kill = setTimeout(() => ctl.abort(), this.o.timeout ?? 10000);
    const t0 = Date.now();
    try {
      let res: Response;
      try {
        res = await this.f(this.url(path), {
          method, signal: ctl.signal,
          headers: { 'Content-Type': 'application/json', ...(this.o.token ? { Authorization: `Bearer ${this.o.token}` } : {}) },
          body: method === 'GET' ? undefined : JSON.stringify(body ?? {}),
        });
      } catch (e: any) { throw new ServiceError(e?.name === 'AbortError' ? 'TIMEOUT' : 'NETWORK', String(e?.message ?? e)); }
      const data: any = await res.json().catch(() => ({}));
      if (!res.ok) throw new ServiceError(data.code ?? `HTTP_${res.status}`, data.message ?? res.statusText, { status: res.status });
      return data;
    } finally {
      clearTimeout(kill);
      if (slow) { clearTimeout(slow); this.o.onSlow!(false); }
      this.stats.lastMs = Date.now() - t0;
    }
  }
  private async call(method: string, path: string, body?: unknown): Promise<any> {
    this.stats.calls++;
    let last: ServiceError | undefined;
    const n = this.o.retries ?? 2;
    for (let i = 0; i <= n; i++) {
      try { return await this.once(method, path, body); } catch (e) {
        last = e as ServiceError;
        this.stats.errors[last.code] = (this.stats.errors[last.code] ?? 0) + 1;
        if (!isRetryable(last.code) || i === n) break;
        this.stats.retries++;
      }
    }
    throw last;
  }
  private async result(method: string, path: string, body?: unknown): Promise<SpinResult> {
    const d = await this.call(method, path, body);
    const r = d && d.schema ? d : d?.result;
    const errs = validateSpinResult(r);
    if (errs.length) throw new ServiceError('SCHEMA_INVALID', `SpinResult 不合契約：${errs[0]}`, { errors: errs });
    return r;
  }
  async init(): Promise<ServiceInfo> { const d = await this.call('POST', 'init', { protocol: PROTOCOL }); return d.info ?? d; }
  async balance(): Promise<number> { return (await this.call('GET', 'balance')).balance; }
  spin(req: SpinRequest) { return this.result('POST', 'spin', { bet: req.bet, requestId: req.requestId ?? newRequestId() }); }
  action(req: ActionRequest) { return this.result('POST', 'action', { ...req, requestId: req.requestId ?? newRequestId() }); }
  ack(roundId: string) { return this.call('POST', 'ack', { roundId }).then(() => true, () => false); }
  fetch(roundId: string) { return this.result('GET', `round/${encodeURIComponent(roundId)}`); }
}

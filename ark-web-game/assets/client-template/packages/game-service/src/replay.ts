// ReplayService（播 .trace.json）與 Recorder（包住任一 Service 錄成 trace）；trace 格式與 Stage 相同（proto-stage-trace/1），兩軌可互播
import { ServiceError, type SpinResult, type Trace } from '@pgp/shared-types';
import type { ActionRequest, GameService, ServiceInfo, SpinRequest } from './types.js';

export class ReplayService implements GameService {
  readonly kind = 'replay' as const;
  readonly debug = null;
  i = 0;
  constructor(readonly trace: Trace) {
    if (trace?.schema !== 'proto-stage-trace/1') throw new ServiceError('BAD_REQUEST', 'trace schema 必須是 proto-stage-trace/1');
  }
  private bal(): number { const r = this.trace.results[this.i - 1]; return r ? r.balanceAfter : Number((this.trace.info as any)?.balance ?? 0); }
  async init(): Promise<ServiceInfo> { return { ...(this.trace.info as object), service: 'replay', pending: null, balance: this.bal() } as ServiceInfo; }
  async balance() { return this.bal(); }
  async spin(req: SpinRequest): Promise<SpinResult> {
    const r = this.trace.results[this.i];
    if (!r) throw new ServiceError('END_OF_TRACE', '軌跡已播完');
    if (req.bet !== undefined && req.bet !== r.bet) throw new ServiceError('INVALID_BET', `軌跡第 ${this.i + 1} 局押注為 ${r.bet}`);
    this.i++;
    return r;
  }
  async action(_: ActionRequest): Promise<SpinResult> { throw new ServiceError('NOT_SUPPORTED', '重播不支援選擇'); }
  async ack() { return true; }
}

export class Recorder implements GameService {
  readonly kind;
  readonly debug: GameService['debug'];
  info: ServiceInfo | null = null;
  results: SpinResult[] = [];
  constructor(readonly svc: GameService) {
    this.kind = svc.kind;
    this.debug = svc.debug ? { force: async (s, o) => { const r = await svc.debug!.force(s, o); this.results.push(r); return r; } } : null;
  }
  get stats() { return this.svc.stats; }
  async init() { this.info = await this.svc.init(); return this.info; }
  balance() { return this.svc.balance(); }
  async spin(req: SpinRequest) { const r = await this.svc.spin(req); this.results.push(r); return r; }
  async action(req: ActionRequest) { const r = await this.svc.action(req); this.results.push(r); return r; }
  ack(roundId: string) { return this.svc.ack(roundId); }
  fetch(roundId: string) { return this.svc.fetch ? this.svc.fetch(roundId) : Promise.reject(new ServiceError('NOT_SUPPORTED', 'fetch')); }
  close() { this.svc.close?.(); }
  trace(): Trace { const info = { ...(this.info ?? {}) } as any; delete info.pending; return { schema: 'proto-stage-trace/1', info, results: this.results.slice() }; }
}

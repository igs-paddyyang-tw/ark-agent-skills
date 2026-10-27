// ArkConn：ark-go WebSocket 連線（auth、sn、ret＋sn 對應、推播、alive、逾時、自動重連）。與 Stage runtime/service/arkconn.js 同行為。
import { createDecoder, encode, type Packet } from './codec.js';

export type ConnState = 'idle' | 'connecting' | 'authed' | 'reconnecting' | 'closed' | 'error';

export class ConnError extends Error {
  constructor(public code: 'NETWORK' | 'TIMEOUT' | 'SESSION_EXPIRED' | 'MISSING_DEP', message: string, public data?: unknown) { super(message); this.name = 'ConnError'; }
}

export interface ArkConnOptions {
  url: string;
  auth: () => { ark_id: string; ark_token: string };
  WebSocket?: typeof WebSocket;
  aliveMs?: number;      // 預設 8000（Server 20 秒沒收到封包以 408 關閉）
  timeoutMs?: number;    // 單一請求逾時，預設 10000
  reconnect?: { delays: number[] };   // 預設 0.5→1→2→4→8 秒
  onState?: (s: ConnState, why?: unknown) => void;
}

type Waiter = { resolve: (d: any) => void; reject: (e: Error) => void; timer: ReturnType<typeof setTimeout>; t0: number };

export class ArkConn {
  readonly o: Required<Omit<ArkConnOptions, 'WebSocket' | 'onState'>> & Pick<ArkConnOptions, 'onState'>;
  private WS: typeof WebSocket;
  private ws: WebSocket | null = null;
  private decode = createDecoder();
  private pending = new Map<string, Waiter>();
  private subs = new Map<string, Set<(d: any) => void>>();
  private aliveTimer: ReturnType<typeof setInterval> | undefined;
  private closedByUser = false;
  private openP: Promise<unknown> | null = null;
  sn = 0;
  state: ConnState = 'idle';
  stats = { sent: 0, recv: 0, reconnects: 0, lastRttMs: 0 };

  constructor(o: ArkConnOptions) {
    this.o = { aliveMs: 8000, timeoutMs: 10000, ...o, reconnect: { delays: [500, 1000, 2000, 4000, 8000], ...(o.reconnect ?? {}) } };
    const W = o.WebSocket ?? (globalThis as any).WebSocket;
    if (!W) throw new ConnError('MISSING_DEP', '環境沒有 WebSocket');
    this.WS = W;
  }

  private setState(s: ConnState, why?: unknown) { this.state = s; this.o.onState?.(s, why); this.emit('', 'state', { state: s, why }); }

  open(): Promise<unknown> {
    this.closedByUser = false;
    return new Promise((resolve, reject) => {
      this.setState('connecting');
      let ws: WebSocket;
      try { ws = new this.WS(this.o.url); } catch (e) { reject(new ConnError('NETWORK', String((e as Error).message ?? e))); return; }
      this.ws = ws;
      this.decode = createDecoder();
      let opened = false;
      ws.onopen = async () => {
        opened = true;
        try {
          const r: any = await this.request(null, 'auth', this.o.auth(), { allowUnauthed: true });
          if (!r || r.status !== 0) throw new ConnError('SESSION_EXPIRED', (r && (r.msg || r.message)) || 'auth 失敗', r);
          this.setState('authed');
          this.startAlive();
          resolve(r);
        } catch (e) { reject(e instanceof ConnError ? e : new ConnError('NETWORK', String(e))); try { ws.close(); } catch { /* 已關 */ } }
      };
      ws.onmessage = (ev) => this.onMessage(typeof ev.data === 'string' ? ev.data : String(ev.data));
      ws.onerror = () => { if (!opened) { reject(new ConnError('NETWORK', `無法連線 ${this.o.url}`)); this.setState('closed', 'connect-failed'); } };
      ws.onclose = (ev) => { if (!opened) reject(new ConnError('NETWORK', `無法連線 ${this.o.url}（${ev?.code ?? ''}）`)); this.onClose(ev, opened); };
    });
  }

  private onMessage(data: string) {
    let pkts: Packet[];
    try { pkts = this.decode(data); } catch (e) { this.setState('error', (e as any).code); try { this.ws?.close(); } catch { /* */ } return; }
    for (const p of pkts) {
      this.stats.recv++;
      if (p.ret) {
        const key = `${p.ret}|${p.sn}`;
        const w = this.pending.get(key);
        if (w) { this.pending.delete(key); clearTimeout(w.timer); this.stats.lastRttMs = Date.now() - w.t0; w.resolve(p.data); }
        continue;
      }
      if (p.cmd) this.emit(p.sys || '', p.cmd, p.data);
    }
  }

  private emit(sys: string, cmd: string, data: unknown) {
    const set = this.subs.get(`${sys}|${cmd}`);
    if (set) for (const fn of [...set]) { try { fn(data); } catch (e) { console.error(e); } }
  }

  private onClose(ev: CloseEvent | undefined, opened: boolean) {
    clearInterval(this.aliveTimer);
    for (const [, w] of this.pending) { clearTimeout(w.timer); w.reject(new ConnError('NETWORK', `連線中斷（${ev?.code ?? ''}）`)); }
    this.pending.clear();
    if (this.closedByUser || !opened) { if (this.state !== 'closed') this.setState('closed', ev?.code); return; }
    void this.reconnect(0);
  }

  private async reconnect(i: number): Promise<void> {
    const d = this.o.reconnect.delays;
    if (i >= d.length) { this.setState('closed', 'reconnect-exhausted'); this.emit('', 'reconnect-failed', null); return; }
    this.setState('reconnecting', i + 1);
    await new Promise((r) => setTimeout(r, d[i]));
    if (this.closedByUser) return;
    try { await this.open(); this.stats.reconnects++; this.emit('', 'reconnected', { attempt: i + 1 }); } catch (e) {
      if ((e as ConnError).code === 'SESSION_EXPIRED') { this.setState('closed', 'SESSION_EXPIRED'); this.emit('', 'auth-expired', e); return; }
      void this.reconnect(i + 1);
    }
  }

  private startAlive() {
    clearInterval(this.aliveTimer);
    this.aliveTimer = setInterval(() => { try { this.send({ cmd: 'alive' }); } catch { /* 關閉中 */ } }, this.o.aliveMs);
  }

  private send(p: Packet) {
    if (!this.ws || this.ws.readyState !== 1) throw new ConnError('NETWORK', '連線未開啟');
    this.ws.send(encode(p));
    this.stats.sent++;
  }

  /** 等連線可用：已認證 → 立即；連線中或重連中（或 socket 已斷但 onclose 未到）→ 等結果，不另開連線（避免 KickSameID）；否則 open */
  ready(): Promise<unknown> {
    const isOpen = this.ws?.readyState === 1;
    if (this.state === 'authed' && isOpen) return Promise.resolve();
    if (this.state === 'connecting' || this.state === 'reconnecting' || (this.state === 'authed' && !isOpen)) {
      return new Promise((resolve, reject) => {
        const off = this.on('', 'state', (d: { state: ConnState }) => {
          if (d.state === 'authed') { off(); resolve(undefined); } else if (d.state === 'closed') { off(); reject(new ConnError('NETWORK', '連線已關閉')); }
        });
      });
    }
    if (!this.openP) this.openP = this.open().finally(() => { this.openP = null; });
    return this.openP;
  }

  /** 送指令並等回應（ret＋sn）；sys 為 null 表示 default system（auth、alive、close） */
  request<T = any>(sys: string | null, cmd: string, data?: unknown, opt: { allowUnauthed?: boolean; timeoutMs?: number } = {}): Promise<T> {
    if (!opt.allowUnauthed && this.state !== 'authed') return Promise.reject(new ConnError('NETWORK', '尚未連線'));
    const sn = ++this.sn;
    return new Promise<T>((resolve, reject) => {
      const key = `${cmd}|${sn}`;
      const timer = setTimeout(() => { this.pending.delete(key); reject(new ConnError('TIMEOUT', `${cmd} 逾時`)); }, opt.timeoutMs ?? this.o.timeoutMs);
      this.pending.set(key, { resolve: (d: any) => { if (d && d.status === -999) { reject(new ConnError('SESSION_EXPIRED', d.msg || 'not authed', d)); return; } resolve(d as T); }, reject, timer, t0: Date.now() });
      try { this.send({ cmd, data, sn, sys }); } catch (e) { clearTimeout(timer); this.pending.delete(key); reject(e as Error); }
    });
  }

  on<T = any>(sys: string | null, cmd: string, fn: (d: T) => void): () => void {
    const k = `${sys || ''}|${cmd}`;
    if (!this.subs.has(k)) this.subs.set(k, new Set());
    this.subs.get(k)!.add(fn);
    return () => { this.subs.get(k)?.delete(fn); };
  }

  /** 測試與除錯用：目前的 socket（模擬斷線） */
  get socket(): WebSocket | null { return this.ws; }

  close() {
    this.closedByUser = true;
    clearInterval(this.aliveTimer);
    try { this.send({ cmd: 'close' }); } catch { /* 已關 */ }
    try { this.ws?.close(); } catch { /* 已關 */ }
  }
}

// ============================================================
//  [ark-game-proto stage] ArkConn：ark-go WebSocket 連線（auth、sn、請求對應、推播、alive、逾時、重連）
//    request(sys, cmd, data) → 回應 data；以 ret（＝原 cmd）＋ sn 對應，sn 每送一包遞增（重試也用新 sn）
//    on(sys, cmd, fn)        → 訂閱推播（例 sys "slot" cmd "result" 分段）
//    auth、alive、close 用 default system（sys 省略）；未認證回 status -999 → SESSION_EXPIRED
//    Server 預設 20 秒沒收到封包以 408 關閉 → 每 aliveMs（預設 8 秒）送 alive
//    斷線自動重連（退避 0.5→1→2→4→8 秒），重連後重新 auth 並發 'reconnected'
//  規格：ark-web-game references/wire-protocol.md
// ============================================================
(function () {
  'use strict';
  const root = typeof window !== 'undefined' ? window : globalThis;
  const Proto = (root.Proto = root.Proto || {});

  class ConnError extends Error {
    constructor(code, message, data) { super(message || code); this.code = code; this.data = data; }
  }

  class ArkConn {
    // o: { url, auth: () => ({ark_id, ark_token}), WebSocket?, aliveMs=8000, timeoutMs=10000, reconnect: {delays}, onState }
    constructor(o) {
      this.o = { aliveMs: 8000, timeoutMs: 10000, ...o, reconnect: { delays: [500, 1000, 2000, 4000, 8000], ...(o.reconnect || {}) } };
      this.WS = o.WebSocket || root.WebSocket;
      if (!this.WS) throw new ConnError('MISSING_DEP', '環境沒有 WebSocket');
      this.sn = 0;
      this.pending = new Map();      // key = cmd|sn → {resolve, reject, timer}
      this.subs = new Map();         // key = sys|cmd → Set(fn)
      this.state = 'idle';
      this.closedByUser = false;
      this.stats = { sent: 0, recv: 0, reconnects: 0, lastRttMs: 0 };
      this.decode = Proto.wire.createDecoder();
    }

    _setState(s, why) { this.state = s; if (this.o.onState) this.o.onState(s, why); this._emit('', 'state', { state: s, why }); }

    // 連線並認證；auth 失敗丟 SESSION_EXPIRED
    open() {
      this.closedByUser = false;
      return new Promise((resolve, reject) => {
        this._setState('connecting');
        let ws;
        try { ws = new this.WS(this.o.url); } catch (e) { reject(new ConnError('NETWORK', String(e.message || e))); return; }
        this.ws = ws;
        this.decode = Proto.wire.createDecoder();
        let opened = false;
        ws.onopen = async () => {
          opened = true;
          try {
            const a = this.o.auth();
            const r = await this.request(null, 'auth', a, { allowUnauthed: true });
            if (!r || r.status !== 0) throw new ConnError('SESSION_EXPIRED', (r && (r.msg || r.message)) || 'auth 失敗', r);
            this._setState('authed');
            this._startAlive();
            resolve(r);
          } catch (e) { reject(e.code ? e : new ConnError('NETWORK', String(e))); try { ws.close(); } catch (_) { /* 已關 */ } }
        };
        ws.onmessage = (ev) => this._onMessage(ev.data);
        ws.onerror = () => { if (!opened) { reject(new ConnError('NETWORK', `無法連線 ${this.o.url}`)); this._setState('closed', 'connect-failed'); } };   // node 的 WebSocket 連不上時只發 error、不發 close
        ws.onclose = (ev) => { if (!opened) reject(new ConnError('NETWORK', `無法連線 ${this.o.url}（${ev && ev.code || ''}）`)); this._onClose(ev, opened); };
      });
    }

    _onMessage(data) {
      let pkts;
      try { pkts = this.decode(typeof data === 'string' ? data : String(data)); } catch (e) { this._setState('error', e.code); try { this.ws.close(); } catch (_) { /* */ } return; }
      for (const p of pkts) {
        this.stats.recv++;
        if (p.ret) {
          const key = `${p.ret}|${p.sn}`;
          const w = this.pending.get(key);
          if (w) { this.pending.delete(key); clearTimeout(w.timer); this.stats.lastRttMs = Date.now() - w.t0; w.resolve(p.data); }
          continue;
        }
        if (p.cmd) this._emit(p.sys || '', p.cmd, p.data);
      }
    }

    _emit(sys, cmd, data) {
      const set = this.subs.get(`${sys}|${cmd}`);
      if (set) for (const fn of [...set]) { try { fn(data); } catch (e) { console.error(e); } }
    }

    _onClose(ev, opened) {
      clearInterval(this.aliveTimer);
      for (const [, w] of this.pending) { clearTimeout(w.timer); w.reject(new ConnError('NETWORK', `連線中斷（${ev && ev.code || ''}）`)); }
      this.pending.clear();
      if (this.closedByUser || !opened) { this._setState('closed', ev && ev.code); return; }
      this._reconnect(0);
    }

    async _reconnect(i) {
      const d = this.o.reconnect.delays;
      if (i >= d.length) { this._setState('closed', 'reconnect-exhausted'); this._emit('', 'reconnect-failed', null); return; }
      this._setState('reconnecting', i + 1);
      await new Promise((r) => setTimeout(r, d[i]));
      if (this.closedByUser) return;
      try { await this.open(); this.stats.reconnects++; this._emit('', 'reconnected', { attempt: i + 1 }); } catch (e) {
        if (e.code === 'SESSION_EXPIRED') { this._setState('closed', 'SESSION_EXPIRED'); this._emit('', 'auth-expired', e); return; }
        this._reconnect(i + 1);
      }
    }

    _startAlive() {
      clearInterval(this.aliveTimer);
      this.aliveTimer = setInterval(() => { try { this._send({ cmd: 'alive' }); } catch (_) { /* 關閉中 */ } }, this.o.aliveMs);
    }

    _send(p) {
      if (!this.ws || this.ws.readyState !== 1) throw new ConnError('NETWORK', '連線未開啟');
      this.ws.send(Proto.wire.encode(p));
      this.stats.sent++;
    }

    // 等連線可用：已認證 → 立即；連線中或自動重連中 → 等結果（不另開連線，避免同帳號互踢 KickSameID）；閒置或已關 → open()
    ready() {
      const open = this.ws && this.ws.readyState === 1;
      if (this.state === 'authed' && open) return Promise.resolve();
      // 已認證但 socket 已斷（onclose 尚未觸發，例：Server 因封包過量 509 關閉）→ 等自動重連的結果
      if (this.state === 'connecting' || this.state === 'reconnecting' || (this.state === 'authed' && !open)) {
        return new Promise((resolve, reject) => {
          const off = this.on('', 'state', ({ state }) => {
            if (state === 'authed') { off(); resolve(); } else if (state === 'closed') { off(); reject(new ConnError('NETWORK', '連線已關閉')); }
          });
        });
      }
      if (!this._openP) this._openP = this.open().finally(() => { this._openP = null; });
      return this._openP;
    }

    // 送一個指令並等回應（ret＋sn）；sys 為 null 表示 default system
    request(sys, cmd, data, opt = {}) {
      if (!opt.allowUnauthed && this.state !== 'authed') return Promise.reject(new ConnError('NETWORK', '尚未連線'));
      const sn = ++this.sn;
      return new Promise((resolve, reject) => {
        const key = `${cmd}|${sn}`;
        const timer = setTimeout(() => { this.pending.delete(key); reject(new ConnError('TIMEOUT', `${cmd} 逾時`)); }, opt.timeoutMs || this.o.timeoutMs);
        this.pending.set(key, { resolve: (d) => {
          if (d && d.status === -999) { reject(new ConnError('SESSION_EXPIRED', d.msg || 'not authed', d)); return; }
          resolve(d);
        }, reject, timer, t0: Date.now() });
        try { this._send({ cmd, data, sn, sys }); } catch (e) { clearTimeout(timer); this.pending.delete(key); reject(e); }
      });
    }

    on(sys, cmd, fn) {
      const k = `${sys || ''}|${cmd}`;
      if (!this.subs.has(k)) this.subs.set(k, new Set());
      this.subs.get(k).add(fn);
      return () => this.subs.get(k).delete(fn);
    }

    close() {
      this.closedByUser = true;
      clearInterval(this.aliveTimer);
      try { this._send({ cmd: 'close' }); } catch (_) { /* 已關 */ }
      try { this.ws && this.ws.close(); } catch (_) { /* 已關 */ }
    }
  }

  Proto.ArkConn = ArkConn;
  Proto.ConnError = ConnError;
})();

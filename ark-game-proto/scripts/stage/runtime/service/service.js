// ============================================================
//  [ark-game-proto stage] GameService：演出層唯一的結果來源
//    init()            → GameInfo（押注、餘額、盤面尺寸、pending）
//    spin({ bet, requestId })   → SpinResult（proto-stage-result/1，一次含玩法劇本）
//    action({ roundId, choice, requestId }) → 選擇型玩法續算（目前內建玩法皆不需要）
//    balance()         → 餘額
//    debug.force(scene) → 情境搜尋（只在開發；Local = 沿數學流往後找自然轉出的局，不改結果）
//  四種實作：LocalService（瀏覽器內引擎）、ReplayService（重播軌跡）、HttpService（Stage HTTP）、WsService（ark-go WebSocket）
//    連線類（Http／Ws）另有 ack(roundId)（演完確認）、fetch(roundId)（補拿）；init 帶 protocol 做版本協商（不相容 PROTOCOL_MISMATCH）
//  原則：結果先決、數學 RNG 與演出 RNG 分流（fx = seed ^ 0x5bd1e995）、金額整數、Service 為餘額權威
// ============================================================
(function () {
  'use strict';
  const root = typeof window !== 'undefined' ? window : globalThis;
  const Proto = root.Proto;
  const R = () => Proto.stageResult;
  const L = () => Proto.slotLogic;
  const FX_XOR = 0x5bd1e995;

  class ServiceError extends Error {
    constructor(code, message, data) {
      super(message || code);
      this.code = code;
      this.data = data;
    }
  }

  const u32 = (rng) => Math.floor(rng() * 4294967296) >>> 0;

  // Go math/rand 的 Float64() 數學流，需載入 ark-game-proto scripts/src/go-rand.js
  //   Go 1 值流（math/rand rand.go）：float64(Int63()) / (1 << 63)，結果為 1.0 時重抽
  //   ⚠️ 1.1.0 誤用 Int63n(1<<53)/2^53（取低 53 位元）＝ Go 原始碼註解裡的「較簡單寫法」，Go 實際沒採用 → 1.1.1 修正
  // 用途：遊戲引擎與 Go Server / Go 快測都以 Float64 依同順序抽值時，同 seed 逐局對帳
  const TWO63 = 9223372036854775808;
  function goFloatRng(seed) {
    const G = root.GoRand || null;
    if (!G) throw new ServiceError('MISSING_DEP', '需要 go-rand.js（GoRand）');
    const g = G.create(Number(seed));
    const f = () => { for (;;) { const v = Number(g.int63()) / TWO63; if (v < 1) return v; } };
    f.int = (n) => g.int(n);
    f.go = g;
    return f;
  }
  // 本用戶端支援的協定版本（init 時送出，Server 不相容回 426 PROTOCOL_MISMATCH）
  const PROTOCOL = { result: 'proto-stage-result/1', info: 'proto-stage-info/1', wire: 'ark-wire/1' };
  const RETRYABLE = /^(NETWORK|TIMEOUT|SERVER_ERROR|HTTP_5)/;
  let reqSeq = 0;
  const newRequestId = () => `q-${Date.now().toString(36)}-${(++reqSeq).toString(36)}`;

  // ---------- Local：瀏覽器內引擎（Proto Logic + 玩法 logic）----------
  class LocalService {
    constructor(spec, opts = {}) {
      this.kind = 'local';
      this.spec = spec;
      this.p = L().prepare(spec);
      this.seed = opts.seed === undefined || opts.seed === null || opts.seed === '' ? Math.floor(Math.random() * 4294967296) >>> 0 : Number(opts.seed) >>> 0;
      // 數學流（整個 session 一條，與 Logic.simulate 相同用法）；opts.rng = 'go' → Go math/rand Float64 流
      this.rngKind = opts.rng === 'go' ? 'go' : typeof opts.rng === 'function' ? 'custom' : 'mulberry32';
      this.rng = opts.rng === 'go' ? goFloatRng(this.seed) : typeof opts.rng === 'function' ? opts.rng : Proto.createRng(this.seed);
      this.fxRng = Proto.createRng((this.seed ^ FX_XOR) >>> 0);    // 演出流
      this.bal = opts.balance ?? 100000;
      this.round = 0;
      this.done = new Map();                                        // requestId → result（冪等）
      this.debug = { force: (scene, o) => this.force(scene, o) };
    }

    async init() {
      const p = this.p;
      return {
        schema: 'proto-stage-info/1', service: this.kind, seed: this.seed, rng: this.rngKind,
        reels: p.reels, rows: p.rows, symbols: p.ids.slice(),
        bets: p.bet.steps.slice(), defaultBet: p.bet.def, betBase: p.bet.base,
        balance: this.bal, feature: p.feature ? p.feature.type : null, pending: null,
      };
    }

    async balance() { return this.bal; }

    // 一局的數學（抽值順序 = Logic.playOne：spinGrid → evaluate → draw → play）
    _play() {
      const p = this.p, Lg = L();
      const g = Lg.spinGrid(p, 'base', this.rng);
      const ev = Lg.evaluate(p, g.grid);
      const fx = u32(this.fxRng);
      let draw = null, res = null, type = null;
      if (ev.trigger) {
        const F = Lg.feature(p);
        if (F) {
          type = p.feature.type;
          draw = F.logic.draw(F.fp, p, this.rng, ev, g);
          res = F.logic.play(F.fp, p, this.rng, draw, ev, g, { record: true, prng: Proto.createRng(fx) });
        }
      }
      return { g, ev, draw, res, type, fx };
    }

    _checkBet(bet) {
      if (!this.p.bet.steps.includes(bet)) throw new ServiceError('INVALID_BET', `押注 ${bet} 不在 ${this.p.bet.steps.join('/')}`);
      if (this.bal < bet) throw new ServiceError('INSUFFICIENT_BALANCE', '餘額不足');
    }

    _settle(m, bet, requestId) {
      this.round++;
      const r = R().build({
        g: m.g, ev: m.ev, draw: m.draw, res: m.res, featureType: m.type, bet,
        betIndex: this.p.bet.steps.indexOf(bet), seed: this.seed, round: this.round,
        roundId: `L${this.seed.toString(16)}-${this.round}`, requestId, fx: m.fx, balanceBefore: this.bal,
      });
      this.bal = r.balanceAfter;
      if (requestId) this.done.set(requestId, r);
      return r;
    }

    async spin(req = {}) {
      const bet = req.bet ?? this.p.bet.def;
      const requestId = req.requestId || newRequestId();
      if (this.done.has(requestId)) return this.done.get(requestId);   // 重送同一個 requestId 不重複扣款
      this._checkBet(bet);
      return this._settle(this._play(), bet, requestId);
    }

    async action() { throw new ServiceError('NOT_SUPPORTED', '此玩法沒有玩家選擇步驟'); }

    // 情境搜尋：沿數學流往後找，直到自然轉出符合條件的局（被跳過的局不計帳）
    //   scene：'feature' | { feature: true, feat: 'OH', group, minX } | function(m) → bool
    async force(scene, o = {}) {
      const bet = o.bet ?? this.p.bet.def;
      this._checkBet(bet);
      const pred = typeof scene === 'function' ? scene : (m) => {
        const s = typeof scene === 'string' ? { feature: scene === 'feature' } : scene || {};
        if (s.feature && !m.res) return false;
        if (s.feat && m.ev.feat !== s.feat) return false;
        if (s.group !== undefined && !(m.draw && String(m.draw.group) === String(s.group))) return false;
        if (s.minX && m.ev.x + (m.res ? m.res.x : 0) < s.minX) return false;
        return true;
      };
      const tries = o.tries ?? 2000000;
      for (let i = 0; i < tries; i++) {
        const m = this._play();
        if (pred(m)) return this._settle(m, bet, o.requestId || newRequestId());
      }
      throw new ServiceError('NOT_FOUND', `${tries} 局內找不到符合條件的局`);
    }
  }

  // ---------- Replay：重播錄好的軌跡（.trace.json）----------
  class ReplayService {
    // opts.loop（1.6.0，引擎回放試玩）：播完從頭再來，餘額接續（每局 balanceBefore／After 依位移重算，結果本身不變）
    constructor(trace, opts = {}) {
      this.kind = 'replay';
      this.trace = trace;
      this.i = 0;
      this.loop = !!(opts.loop || trace.loop);
      this.offset = 0;
      this.last = null;
      this.debug = null;
    }
    async init() { return { ...(this.trace.info || {}), service: this.kind, pending: null, balance: this._bal() }; }
    _bal() { return this.last ? this.last.balanceAfter : (this.trace.info || {}).balance ?? 0; }
    async balance() { return this._bal(); }
    async spin(req = {}) {
      const R = this.trace.results;
      if (this.i >= R.length && this.loop && R.length) { this.offset = this._bal() - R[0].balanceBefore; this.i = 0; }
      let r = R[this.i];
      if (!r) throw new ServiceError('END_OF_TRACE', '軌跡已播完');
      if (req.bet !== undefined && req.bet !== r.bet) throw new ServiceError('INVALID_BET', `軌跡第 ${this.i + 1} 局押注為 ${r.bet}`);
      this.i++;
      if (this.offset) r = { ...r, balanceBefore: r.balanceBefore + this.offset, balanceAfter: r.balanceAfter + this.offset };
      this.last = r;
      return r;
    }
    async action() { throw new ServiceError('NOT_SUPPORTED', '重播不支援選擇'); }
  }

  // ---------- Http：slot-bot server（API-101～105）----------
  class HttpService {
    constructor(opts = {}) {
      this.kind = 'http';
      this.base = (opts.base || '').replace(/\/$/, '');
      this.gameId = opts.gameId;
      this.token = opts.token || null;
      this.timeout = opts.timeout ?? 10000;
      this.retries = opts.retries ?? 2;
      this.fetch = opts.fetch || (typeof fetch !== 'undefined' ? fetch.bind(root) : null);
      this.onSlow = opts.onSlow || null;
      this.debug = opts.dev ? { force: (scene, o = {}) => this._call('POST', 'dev/force', { scene, ...o }) } : null;
      this.stats = { calls: 0, retries: 0, errors: {}, lastMs: 0 };
    }
    url(path) { return `${this.base}/api/slot/${encodeURIComponent(this.gameId)}/${path}`; }
    async _once(method, path, body) {
      const ctl = typeof AbortController !== 'undefined' ? new AbortController() : null;
      const slow = this.onSlow ? setTimeout(() => this.onSlow(true), 3000) : null;
      const kill = setTimeout(() => ctl && ctl.abort(), this.timeout);
      const t0 = Date.now();
      try {
        const res = await this.fetch(this.url(path), {
          method, signal: ctl ? ctl.signal : undefined,
          headers: { 'Content-Type': 'application/json', ...(this.token ? { Authorization: `Bearer ${this.token}` } : {}) },
          body: method === 'GET' ? undefined : JSON.stringify(body || {}),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new ServiceError(data.code || `HTTP_${res.status}`, data.message || res.statusText, { status: res.status });
        return data;
      } finally {
        clearTimeout(kill);
        if (slow) { clearTimeout(slow); this.onSlow(false); }
        this.stats.lastMs = Date.now() - t0;
      }
    }
    async _call(method, path, body) {
      this.stats.calls++;
      let last;
      for (let i = 0; i <= this.retries; i++) {
        try { return await this._once(method, path, body); } catch (e) {
          last = e;
          const code = e.code || 'NETWORK';
          this.stats.errors[code] = (this.stats.errors[code] || 0) + 1;
          const retryable = !(e instanceof ServiceError) || /^HTTP_5|SERVER_ERROR/.test(e.code);
          if (!retryable || i === this.retries) break;
          this.stats.retries++;
        }
      }
      throw last instanceof ServiceError ? last : new ServiceError('NETWORK', String(last && last.message || last));
    }
    init() { return this._call('POST', 'init', { protocol: PROTOCOL }); }
    balance() { return this._call('GET', 'balance').then((d) => d.balance); }
    spin(req = {}) { return this._call('POST', 'spin', { bet: req.bet, requestId: req.requestId || newRequestId() }); }   // 重試沿用同一個 requestId（冪等）
    action(req = {}) { return this._call('POST', 'action', { ...req, requestId: req.requestId || newRequestId() }); }
    ack(roundId) { return this._call('POST', 'ack', { roundId }).then(() => true, () => false); }   // 失敗不擋遊戲：下次 init 會再帶 pending
    fetch(roundId) { return this._call('GET', `round/${encodeURIComponent(roundId)}`); }
  }

  // ---------- Ws：ark-go WebSocket（sys "slot"；ark-web-game references/wire-protocol.md）----------
  //   opts: { url, gameId, arkId, token, timeout=10000, retries=2, dev, onSlow, onState, WebSocket, protocol }
  class WsService {
    constructor(opts = {}) {
      this.kind = 'ws';
      this.o = { timeout: 10000, retries: 2, ...opts };
      this.protocol = opts.protocol || PROTOCOL;
      this.conn = new Proto.ArkConn({
        url: opts.url, WebSocket: opts.WebSocket, timeoutMs: this.o.timeout, aliveMs: opts.aliveMs, reconnect: opts.reconnect,
        auth: () => ({ ark_id: String(opts.arkId || 'anon'), ark_token: String(opts.token || 'dev') }), onState: opts.onState,
      });
      this.parts = new Map();                                       // roundId → [{i, n, part}]
      this.conn.on('slot', 'result', (d) => { if (!d || !d.roundId) return; if (!this.parts.has(d.roundId)) this.parts.set(d.roundId, []); this.parts.get(d.roundId).push(d); });
      this.debug = opts.dev ? { force: (scene, o = {}) => this._spinLike('force', { scene, bet: o.bet, requestId: o.requestId || newRequestId() }) } : null;
      this.stats = { calls: 0, retries: 0, errors: {}, lastMs: 0, chunked: 0, fetched: 0 };
    }

    async _ensure() {
      try { await this.conn.ready(); } catch (e) { throw new ServiceError(e.code || 'NETWORK', e.message, e.data); }
    }

    async _once(cmd, data) {
      await this._ensure();
      const slow = this.o.onSlow ? setTimeout(() => this.o.onSlow(true), 3000) : null;
      const t0 = Date.now();
      try {
        const d = await this.conn.request('slot', cmd, data, { timeoutMs: this.o.timeout });
        if (!d || d.status !== 0) {
          const st = d && d.status;
          throw new ServiceError((d && d.code) || (st === -999 ? 'SESSION_EXPIRED' : `WS_${st}`), (d && (d.message || d.msg)) || 'WS 錯誤', { status: st, data: d && d.data });
        }
        return d;
      } catch (e) {
        throw e instanceof ServiceError ? e : new ServiceError(e.code || 'NETWORK', e.message, e.data);
      } finally {
        if (slow) { clearTimeout(slow); this.o.onSlow(false); }
        this.stats.lastMs = Date.now() - t0;
      }
    }

    async _req(cmd, data) {
      this.stats.calls++;
      let last;
      for (let i = 0; i <= this.o.retries; i++) {
        try { return await this._once(cmd, data); } catch (e) {                    // 重試：同 requestId、新 sn（ArkConn 每包遞增）
          last = e;
          this.stats.errors[e.code] = (this.stats.errors[e.code] || 0) + 1;
          if (!RETRYABLE.test(e.code) || i === this.o.retries) break;
          this.stats.retries++;
          await new Promise((r) => setTimeout(r, 200 * (i + 1)));            // 給自動重連一點時間
        }
      }
      throw last;
    }

    // 分段組回：依 i 排序、檢查段數與總字元數；缺段 → fetch 補拿
    async _assemble(d, depth = 0) {
      const got = (this.parts.get(d.roundId) || []).sort((a, b) => a.i - b.i);
      this.parts.delete(d.roundId);
      const text = got.map((x) => x.part).join('');
      if (got.length === d.chunks && (d.chars === undefined || text.length === d.chars)) { this.stats.chunked++; return JSON.parse(text); }
      if (depth > 0) throw new ServiceError('RESULT_INCOMPLETE', `分段不完整（${got.length}/${d.chunks}）`);
      this.stats.fetched++;
      const f = await this._req('fetch', { roundId: d.roundId });
      return f.result !== undefined ? f.result : this._assemble(f, depth + 1);
    }

    async _spinLike(cmd, data) {
      const d = await this._req(cmd, data);
      const r = d.result !== undefined ? d.result : await this._assemble(d);
      const errs = R().validate(r);
      if (errs.length) throw new ServiceError('SCHEMA_INVALID', `SpinResult 不合契約：${errs[0]}`, { errors: errs });
      return r;
    }

    async init() { return (await this._req('init', { protocol: this.protocol })).info; }
    async balance() { return (await this._req('balance')).balance; }
    spin(req = {}) { return this._spinLike('spin', { bet: req.bet, requestId: req.requestId || newRequestId() }); }
    action(req = {}) { return this._spinLike('action', { ...req, requestId: req.requestId || newRequestId() }); }
    ack(roundId) { return this._req('ack', { roundId }).then(() => true, () => false); }
    fetch(roundId) { return this._spinLike('fetch', { roundId }); }
    close() { this.conn.close(); }
  }

  // 錄製：包住任一 Service，把結果存成 .trace.json（ReplayService 直接讀）
  class Recorder {
    constructor(svc) {
      this.svc = svc; this.info = null; this.results = []; this.kind = svc.kind;
      this.debug = svc.debug ? { force: async (s, o) => { const r = await svc.debug.force(s, o); this.results.push(r); return r; } } : null;
    }
    async init() { this.info = await this.svc.init(); return this.info; }
    balance() { return this.svc.balance(); }
    async spin(req) { const r = await this.svc.spin(req); this.results.push(r); return r; }
    async action(req) { const r = await this.svc.action(req); this.results.push(r); return r; }
    ack(roundId) { return this.svc.ack ? this.svc.ack(roundId) : Promise.resolve(false); }
    trace() { return { schema: 'proto-stage-trace/1', info: this.info, results: this.results.slice() }; }
  }

  // 斷線續玩：init 帶回未 ack 的局 → 先完整播放、以 balanceAfter 校正餘額、ack，之後才開放 SPIN
  async function playPending(app) {
    const pend = app.info && app.info.pending;
    if (!pend || !app.module || !app.module.play) return false;
    const m = app.module, st = m.state || {};
    st.busy = true;
    try { await m.play(pend); } catch (e) { if (!e || !e.cancelled) console.error(e); }
    st.balance = pend.balanceAfter;
    st.busy = false;
    if (m.renderHud) m.renderHud();
    if (app.service && app.service.ack) await app.service.ack(pend.roundId);
    return true;
  }
  Proto.playPending = playPending;

  Proto.svc = { ServiceError, LocalService, ReplayService, HttpService, WsService, Recorder, newRequestId, FX_XOR, goFloatRng, PROTOCOL };
})();

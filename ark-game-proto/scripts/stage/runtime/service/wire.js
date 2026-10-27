// ============================================================
//  [ark-game-proto stage] WireCodec：ark-go wire 協定（相容 Python GameSocket2）的編解碼
//    封包 = [長度：4 位數十進位補零][JSON]；長度是「字元數」（Go 以 rune 計）
//    送出：非 ASCII 一律轉 \uXXXX（超出 BMP 用 surrogate pair，小寫 hex，與 Go escapeNonASCII 相同），字元數＝位元組數
//    單包上限 9,999 字元；超過丟 WIRE_TOO_LARGE（Go 端同樣拒送）
//    鍵順序 cmd → ret → data → sn → sys；值為 null／undefined 的鍵不放（與 Python encodeCmd／encodeRet 相同）
//  規格：ark-web-game references/wire-protocol.md；黃金封包：tests/fixtures/wire-golden.json（Go 實跑產生）
// ============================================================
(function () {
  'use strict';
  const root = typeof window !== 'undefined' ? window : globalThis;
  const Proto = (root.Proto = root.Proto || {});
  const HEADER = 4;
  const MAX_BODY = 9999;

  class WireError extends Error {
    constructor(code, message) { super(message || code); this.code = code; }
  }

  const escapeNonASCII = (s) => s.replace(/[\u0080-￿]/g, (c) => '\\u' + c.charCodeAt(0).toString(16).padStart(4, '0'));

  function body(p) {
    const parts = [];
    const put = (k, v) => parts.push(`"${k}":${v}`);
    if (p.cmd) put('cmd', JSON.stringify(String(p.cmd)));
    if (p.ret) put('ret', JSON.stringify(String(p.ret)));
    if (p.data !== undefined && p.data !== null) put('data', JSON.stringify(p.data));
    if (p.sn !== undefined && p.sn !== null) put('sn', JSON.stringify(p.sn));
    if (p.sys !== undefined && p.sys !== null) put('sys', JSON.stringify(String(p.sys)));
    return escapeNonASCII(`{${parts.join(',')}}`);
  }

  // 封包 → 4 位數長度 + JSON
  function encode(p) {
    const b = body(p);
    if (b.length > MAX_BODY) throw new WireError('WIRE_TOO_LARGE', `封包 ${b.length} 字元超過 ${MAX_BODY}`);
    return String(b.length).padStart(HEADER, '0') + b;
  }

  // 有狀態的切包器：一則 WebSocket 訊息可能含多個封包，也可能只有半個。回傳完整切出的封包物件陣列。
  function createDecoder() {
    let buf = '';
    return function feed(chunk) {
      buf += typeof chunk === 'string' ? chunk : new TextDecoder().decode(chunk);
      const out = [];
      for (;;) {
        if ([...buf.slice(0, HEADER + 1)].length <= HEADER) break;        // Python：while len(buffer) > header_len
        const head = buf.slice(0, HEADER);
        if (!/^\d{4}$/.test(head)) { buf = ''; throw new WireError('WIRE_BAD_HEADER', `長度前綴不是 4 位數字：${JSON.stringify(head)}`); }
        const n = Number(head);
        let off = HEADER, cnt = 0;                                          // 以 code point 計（= Go rune）
        while (cnt < n && off < buf.length) { off += buf.codePointAt(off) > 0xffff ? 2 : 1; cnt++; }
        if (cnt < n) break;                                                 // 收到一半
        const text = buf.slice(HEADER, off);
        buf = buf.slice(off);
        let pkt;
        try { pkt = JSON.parse(text); } catch (e) { throw new WireError('WIRE_BAD_JSON', `封包 JSON 錯誤：${e.message}`); }
        out.push(pkt);
      }
      return out;
    };
  }

  Proto.wire = { encode, createDecoder, escapeNonASCII, WireError, HEADER, MAX_BODY };
})();

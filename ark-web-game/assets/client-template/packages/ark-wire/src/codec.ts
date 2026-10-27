// WireCodec：ark-go wire 協定編解碼（TS 版；與 Stage runtime/service/wire.js 同規則、同一組 Go 黃金封包測試）
//   封包 = [長度：4 位數十進位補零][JSON]；長度是字元數（Go rune）；送出非 ASCII 轉 \uXXXX（小寫 hex、surrogate pair）
//   鍵順序 cmd → ret → data → sn → sys；null／undefined 的鍵不放；單包上限 9,999 字元
export interface Packet { cmd?: string; ret?: string; data?: unknown; sn?: number | string; sys?: string | null }

export const HEADER = 4;
export const MAX_BODY = 9999;

export class WireError extends Error {
  constructor(public code: 'WIRE_TOO_LARGE' | 'WIRE_BAD_HEADER' | 'WIRE_BAD_JSON', message: string) { super(message); this.name = 'WireError'; }
}

export const escapeNonASCII = (s: string): string => s.replace(/[\u0080-￿]/g, (c) => '\\u' + c.charCodeAt(0).toString(16).padStart(4, '0'));

function body(p: Packet): string {
  const parts: string[] = [];
  const put = (k: string, v: string) => parts.push(`"${k}":${v}`);
  if (p.cmd) put('cmd', JSON.stringify(String(p.cmd)));
  if (p.ret) put('ret', JSON.stringify(String(p.ret)));
  if (p.data !== undefined && p.data !== null) put('data', JSON.stringify(p.data));
  if (p.sn !== undefined && p.sn !== null) put('sn', JSON.stringify(p.sn));
  if (p.sys !== undefined && p.sys !== null) put('sys', JSON.stringify(String(p.sys)));
  return escapeNonASCII(`{${parts.join(',')}}`);
}

export function encode(p: Packet): string {
  const b = body(p);
  if (b.length > MAX_BODY) throw new WireError('WIRE_TOO_LARGE', `封包 ${b.length} 字元超過 ${MAX_BODY}`);
  return String(b.length).padStart(HEADER, '0') + b;
}

/** 有狀態切包器：一則訊息可能含多個封包或半個；回傳完整切出的封包 */
export function createDecoder(): (chunk: string) => Packet[] {
  let buf = '';
  return (chunk: string) => {
    buf += chunk;
    const out: Packet[] = [];
    for (;;) {
      if ([...buf.slice(0, HEADER + 1)].length <= HEADER) break;
      const head = buf.slice(0, HEADER);
      if (!/^\d{4}$/.test(head)) { buf = ''; throw new WireError('WIRE_BAD_HEADER', `長度前綴不是 4 位數字：${JSON.stringify(head)}`); }
      const n = Number(head);
      let off = HEADER, cnt = 0;
      while (cnt < n && off < buf.length) { off += (buf.codePointAt(off) ?? 0) > 0xffff ? 2 : 1; cnt++; }
      if (cnt < n) break;
      const text = buf.slice(HEADER, off);
      buf = buf.slice(off);
      try { out.push(JSON.parse(text) as Packet); } catch (e) { throw new WireError('WIRE_BAD_JSON', `封包 JSON 錯誤：${(e as Error).message}`); }
    }
    return out;
  };
}

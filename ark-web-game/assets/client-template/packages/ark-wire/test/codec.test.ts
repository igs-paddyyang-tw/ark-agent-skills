// WireCodec：與 Go EncodeFrame 黃金封包逐字相同（fixtures 由 go-server tools/wiregolden 產生）
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { createDecoder, encode, escapeNonASCII, WireError } from '../src/codec.js';

const G = JSON.parse(readFileSync(new URL('./fixtures/wire-golden.json', import.meta.url), 'utf8'));
const pad = (n: number) => { const base = encode({ cmd: 'x', data: '' }).length - 4; return { cmd: 'x', data: 'a'.repeat(n - base) }; };

describe('codec', () => {
  it('編碼與 Go 黃金封包逐字相同', () => { for (const c of G.cases) expect(encode(c.packet), c.name).toBe(c.frame); });
  it('半包、黏包（每 7 字元切一次）解回原封包', () => {
    const dec = createDecoder();
    const all = G.cases.map((c: any) => c.frame).join('');
    const got: unknown[] = [];
    for (let i = 0; i < all.length; i += 7) got.push(...dec(all.slice(i, i + 7)));
    expect(got).toEqual(G.cases.map((c: any) => c.packet));
  });
  it('9,999 字元可送、10,000 拒送（與 Go 同）', () => {
    expect(encode(pad(9999)).length).toBe(G.max9999.frameLen);
    expect(encode(pad(9999)).slice(0, 4)).toBe(G.max9999.header);
    expect(() => encode(pad(10000))).toThrow(WireError);
    expect(G.tooLarge10000).toBe(true);
  });
  it('非 ASCII 轉 \\uXXXX；長度以字元計', () => {
    expect(escapeNonASCII('中')).toBe('\\u4e2d');
    const f = encode({ cmd: 'x', data: '中文' });
    const b = '{"cmd":"x","data":"\\u4e2d\\u6587"}';
    expect(f).toBe(String(b.length).padStart(4, '0') + b);
    expect(createDecoder()(f)).toEqual([{ cmd: 'x', data: '中文' }]);
  });
  it('長度前綴錯誤 → WIRE_BAD_HEADER', () => {
    try { createDecoder()('abcd{}'); expect.unreachable(); } catch (e) { expect((e as WireError).code).toBe('WIRE_BAD_HEADER'); }
  });
});

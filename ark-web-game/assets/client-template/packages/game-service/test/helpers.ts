import { readFileSync } from 'node:fs';
// @ts-ignore 純 JS 測試工具
import { createMockArk } from '@pgp/ark-wire/test/mock-ark';
export const TRACE = JSON.parse(readFileSync(new URL('./fixtures/huff-trace.json', import.meta.url), 'utf8'));
const normal = TRACE.results.slice(0, 40);
const feats = TRACE.results.slice(40);
/** mock ark-go Server，結果取自 huff 軌跡（LocalService rng=go seed 7；與 Go 逐局一致） */
export function huffMock(o: any = {}) {
  let k = 0;
  return createMockArk({
    ...o,
    play: ({ scene, n }: any) => {
      const src = scene ? feats[(k++) % feats.length] : normal[n % normal.length];
      return { ...structuredClone(src), roundId: `R${(n + 1).toString(36)}-${(1e15 + n).toString(16)}` };
    },
  });
}

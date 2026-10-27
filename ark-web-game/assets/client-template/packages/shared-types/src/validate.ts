// SpinResult 輕量驗證（與 Stage Proto.stageResult.validate 同規則）：交給遊戲模組前必驗。
import type { SpinResult } from './index.js';
const isInt = (v: unknown): v is number => Number.isInteger(v);
export function validateSpinResult(r: unknown): string[] {
  const e: string[] = [];
  const need = (c: boolean, m: string) => { if (!c) e.push(m); };
  if (!r || typeof r !== 'object') return ['不是物件'];
  const x = r as Record<string, any>;
  need(x.schema === 'proto-stage-result/1', 'schema 必須是 proto-stage-result/1');
  need(typeof x.roundId === 'string' && x.roundId.length > 0, 'roundId 必填字串');
  for (const k of ['bet', 'totalWin', 'balanceBefore', 'balanceAfter', 'fx']) need(isInt(x[k]), `${k} 必須是整數 credit`);
  need(x.bet > 0, 'bet 必須 > 0');
  need(x.totalWin >= 0, 'totalWin 不可為負');
  need(x.reel && Array.isArray(x.reel.stops) && Array.isArray(x.reel.grid), 'reel.stops / reel.grid 必填');
  need(x.base && isInt(x.base.win) && Array.isArray(x.base.ways), 'base.win 與 base.ways 必填');
  if (x.feature) {
    need(typeof x.feature.type === 'string' && isInt(x.feature.win) && x.feature.script && typeof x.feature.script === 'object', 'feature.type / win / script 必填');
    need(x.totalWin === x.base.win + x.feature.win || !!x.feature.awaitAction, 'totalWin ≠ base.win + feature.win');
  } else if (x.base) need(x.totalWin === x.base.win, 'totalWin ≠ base.win（無玩法）');
  need(x.balanceAfter === x.balanceBefore - x.bet + x.totalWin, 'balanceAfter ≠ balanceBefore − bet + totalWin');
  return e;
}
export type { SpinResult };

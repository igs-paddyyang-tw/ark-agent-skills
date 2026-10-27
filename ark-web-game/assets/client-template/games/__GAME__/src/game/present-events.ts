// present-events/1：演出事件。兩軌（Stage slot/module.js play()／正式 Client）播同一份 SpinResult，事件序列必須相同；值只取自 SpinResult
import type { SpinResult } from '@pgp/shared-types';

export type PresentEvent =
  | { type: 'round-start'; roundId: string; bet: number }
  | { type: 'reels-stop'; roundId: string; stops: number[] }
  | { type: 'base-win'; roundId: string; win: number; ways: number }
  | { type: 'feature-start'; roundId: string; feature: string; spinsPlayed: number | undefined }
  | { type: 'feature-end'; roundId: string; win: number }
  | { type: 'round-end'; roundId: string; totalWin: number; balanceAfter: number };
export const PRESENT_EVENTS_SCHEMA = 'present-events/1';

/** 純函式：一局應有的事件序列（測試與對帳用；遊戲在對應演出時點逐一送出同樣內容） */
export function expectedEvents(r: SpinResult): PresentEvent[] {
  const id = r.roundId;
  const out: PresentEvent[] = [{ type: 'round-start', roundId: id, bet: r.bet }, { type: 'reels-stop', roundId: id, stops: r.reel.stops.slice() }];
  if (r.base.win > 0) out.push({ type: 'base-win', roundId: id, win: r.base.win, ways: r.base.ways.length });
  if (r.feature) {
    out.push({ type: 'feature-start', roundId: id, feature: r.feature.type, spinsPlayed: (r.feature as any).spinsPlayed });
    out.push({ type: 'feature-end', roundId: id, win: r.feature.win });
  }
  out.push({ type: 'round-end', roundId: id, totalWin: r.totalWin, balanceAfter: r.balanceAfter });
  return out;
}

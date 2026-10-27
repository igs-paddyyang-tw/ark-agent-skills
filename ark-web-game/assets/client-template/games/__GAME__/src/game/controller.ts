// GameController：一局的流程（與畫面無關，可在 node 測）。Stage slot/module.js spin()／play() 的 TS 版
//   SPIN → 先扣押注（樂觀）→ service.spin → 驗證 → play（演出、送 present-events）→ 餘額改用 balanceAfter（權威值）→ ack
//   續玩：init 帶回 pending → 先完整播放、以 balanceAfter 校正、ack，之後才開放 SPIN
import { ServiceError, validateSpinResult, type SpinResult } from '@pgp/shared-types';
import type { GameService, ServiceInfo } from '@pgp/game-service';
import type { Clock } from '../runtime/clock.js';
import { Emitter } from '../runtime/events.js';
import type { PresentEvent } from './present-events.js';

export interface HudState { balance: number; bet: number; bets: number[]; win: number; busy: boolean; auto: boolean; message: string }
export interface View {
  render(hud: HudState): void;
  spinStart(): void;
  /** 拿不到結果：停止空轉、回到上一局畫面 */
  abortSpin(): void;
  land(r: SpinResult): Promise<void>;
  showWins(r: SpinResult): Promise<void>;
  countWin(win: number, bet: number): Promise<void>;
  feature(r: SpinResult): Promise<void>;
  clearWins(): void;
}
export type GameEvents = { present: PresentEvent; error: ServiceError; settled: SpinResult };

export class GameController {
  readonly events = new Emitter<GameEvents>();
  readonly hud: HudState = { balance: 0, bet: 0, bets: [], win: 0, busy: true, auto: false, message: '' };
  history: { roundId: string; win: number; feature: string }[] = [];
  spins = 0;
  constructor(readonly service: GameService, readonly view: View, readonly clock: Clock) {}

  /** init 結果套用到 HUD；有 pending 先播完再開放 */
  async start(info: ServiceInfo): Promise<void> {
    const i = info as any;
    this.hud.bets = (i.bets ?? i.bet?.list ?? []).slice();
    this.hud.bet = i.defaultBet ?? i.bet?.def ?? this.hud.bets[0] ?? 0;
    this.hud.balance = Number(i.balance ?? 0);
    if (info.pending) {
      this.hud.message = '續玩上一局';
      this.view.render(this.hud);
      await this.play(info.pending);
      this.hud.balance = info.pending.balanceAfter;
      await this.service.ack(info.pending.roundId);
    }
    this.hud.busy = false;
    this.hud.message = '';
    this.view.render(this.hud);
  }

  setBet(bet: number) { if (!this.hud.busy && this.hud.bets.includes(bet)) { this.hud.bet = bet; this.view.render(this.hud); } }
  stepBet(d: 1 | -1) { const i = this.hud.bets.indexOf(this.hud.bet); const n = this.hud.bets[Math.max(0, Math.min(this.hud.bets.length - 1, i + d))]; if (n !== undefined) this.setBet(n); }

  async spin(): Promise<SpinResult | null> {
    const h = this.hud;
    if (h.busy) return null;
    if (h.bet > h.balance) { h.message = '餘額不足'; this.view.render(h); return null; }
    h.busy = true; h.win = 0; h.message = '';
    h.balance -= h.bet;                                       // 樂觀扣款；結算以 balanceAfter 為準
    this.view.clearWins();
    this.view.spinStart();
    this.view.render(h);
    let r: SpinResult;
    try {
      r = await this.service.spin({ bet: h.bet });
      const errs = validateSpinResult(r);
      if (errs.length) throw new ServiceError('SCHEMA_INVALID', errs[0]);
    } catch (e) {
      const err = e instanceof ServiceError ? e : new ServiceError('NETWORK', String(e));
      h.balance += h.bet;
      h.busy = false; h.auto = false;
      h.message = `無法完成這一局（${err.code}）`;
      this.events.emit('error', err);
      this.view.render(h);
      this.view.abortSpin();
      return null;
    }
    await this.play(r);
    h.balance = r.balanceAfter;
    h.busy = false;
    this.view.render(h);
    void this.service.ack(r.roundId);                         // 失敗不擋（下次 init 會帶 pending）
    this.events.emit('settled', r);
    if (h.auto) void this.clock.wait(0.35).then(() => { if (h.auto && !h.busy) void this.spin(); });
    return r;
  }

  /** 播一份 SpinResult（ws／http／replay／續玩都走這裡）；present-events 與 Stage 同序同值 */
  async play(r: SpinResult): Promise<void> {
    this.spins++;
    const pe = (e: PresentEvent) => this.events.emit('present', e);
    const id = r.roundId;
    pe({ type: 'round-start', roundId: id, bet: r.bet });
    await this.view.land(r);
    pe({ type: 'reels-stop', roundId: id, stops: r.reel.stops.slice() });
    if (r.base.win > 0) {
      pe({ type: 'base-win', roundId: id, win: r.base.win, ways: r.base.ways.length });
      await this.view.showWins(r);
      this.hud.win = r.base.win;
      await this.view.countWin(r.base.win, r.bet);
    }
    if (r.feature) {
      pe({ type: 'feature-start', roundId: id, feature: r.feature.type, spinsPlayed: (r.feature as any).spinsPlayed });
      await this.view.feature(r);
      this.hud.win = r.totalWin;
      pe({ type: 'feature-end', roundId: id, win: r.feature.win });
    }
    this.hud.win = r.totalWin;
    pe({ type: 'round-end', roundId: id, totalWin: r.totalWin, balanceAfter: r.balanceAfter });
    this.history.unshift({ roundId: id, win: r.totalWin, feature: r.feature ? r.feature.type : '' });
    if (this.history.length > 200) this.history.pop();
  }
}

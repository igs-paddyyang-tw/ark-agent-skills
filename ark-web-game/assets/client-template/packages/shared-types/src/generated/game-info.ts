/* 由 schemas/game-info.schema.json 產生（pnpm gen:types），勿手改 */

/**
 * init 回傳的遊戲資訊。不得含數學 seed（Local 模式可帶，Server 模式不帶）、輪帶、權重。pending 為未 ack 的局（斷線續玩），supported 為 Server 支援的協定版本（協商用）。規則見 ark-web-game references/wire-protocol.md。
 */
export interface GameInfoInitArkGameProtoStageServer {
  schema: 'proto-stage-info/1';
  /**
   * local | http | ws | go | replay
   */
  service: string;
  game?: string;
  /**
   * odds._meta.profile（例 kb-v1、trial-ref）
   */
  profile?: string;
  reels: number;
  rows: number;
  symbols?: string[];
  /**
   * @minItems 1
   */
  bets: [number, ...number[]];
  defaultBet: number;
  betBase?: number;
  balance: number;
  feature?: string | null;
  pending: null | SpinResultArkGameProtoStage;
  /**
   * { result: [...], info: [...], wire: [...] }
   */
  supported?: {
    [k: string]: string[];
  };
  rng?: string;
  /**
   * 只在 Local 模式出現
   */
  seed?: number | null;
  [k: string]: unknown;
}
/**
 * 一局完整結果：主遊戲盤面、連線、玩法劇本、帳務。金額一律整數 credit（floor(倍數 × bet)）。對齊 docs/designs/2026-09-18-spinresult-config-contract-alignment.md。Server 模式 seed 可為 null（不外洩數學種子），fx 為純演出種子。
 */
export interface SpinResultArkGameProtoStage {
  schema: 'proto-stage-result/1';
  roundId: string;
  /**
   * 冪等鍵；同一 requestId 重送回同一結果、不重複扣款
   */
  requestId?: string | null;
  round?: number | null;
  seed?: number | null;
  bet: number;
  betIndex?: number | null;
  mode: 'base';
  reel: {
    combo?: number | string;
    stops: number[];
    /**
     * [軸][列]
     */
    grid: string[][];
    /**
     * 盤面後處理前的原盤面（例：神秘圖騰變身前）
     */
    view?: unknown[] | null;
    [k: string]: unknown;
  };
  base: {
    winX?: number;
    win: number;
    ways: {
      sym: string;
      len: number;
      ways?: number | null;
      line?: number | null;
      winX?: number;
      win: number;
      cells: [number, number][];
      [k: string]: unknown;
    }[];
    scatter?: {
      [k: string]: unknown;
    } | null;
    trigger: boolean;
    /**
     * 遊戲專屬主遊戲欄位（例 HuffNPuff：feat、scCount、scCnt）
     */
    extra?: {
      [k: string]: unknown;
    };
    [k: string]: unknown;
  };
  feature: null | {
    type: string;
    draw?: {
      [k: string]: unknown;
    };
    group?: string | null;
    winX?: number;
    win: number;
    capped?: boolean;
    spinsPlayed?: number | null;
    /**
     * 玩法劇本（logic.play record:true 的回傳，去掉 x 與 strips）；Presenter 唯一輸入
     */
    script: {
      [k: string]: unknown;
    };
    /**
     * 選擇型玩法：等待玩家選擇（options、roundId）
     */
    awaitAction?: {
      [k: string]: unknown;
    } | null;
    [k: string]: unknown;
  };
  totalX?: number;
  totalWin: number;
  capped?: boolean;
  winType: 'NO_WIN' | 'NORMAL' | 'LIGHT' | 'SMALL' | 'BIG' | 'MEGA' | 'SUPER' | 'GOLDEN';
  balanceBefore: number;
  /**
   * = balanceBefore − bet + totalWin；Server 模式為權威值
   */
  balanceAfter: number;
  /**
   * 演出亂數種子（純演出，不影響結果）
   */
  fx: number;
  [k: string]: unknown;
}

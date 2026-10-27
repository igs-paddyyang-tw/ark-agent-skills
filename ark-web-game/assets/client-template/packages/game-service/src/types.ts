// GameService：遊戲模組只認這個介面（結果從哪來＝Service 決定）。與 Stage Proto.svc 的五個 Service 同介面（契約：ark-web-game references/result-contract.md）
import type { GameInfo, SpinResult, Trace } from '@pgp/shared-types';

export type ServiceKind = 'ws' | 'http' | 'replay' | 'local';
export interface SpinRequest { bet: number; requestId?: string }
export interface ActionRequest { roundId: string; choice: unknown; requestId?: string }
export interface ServiceStats { calls: number; retries: number; errors: Record<string, number>; lastMs: number; chunked?: number; fetched?: number }
export type ServiceInfo = GameInfo & { pending?: SpinResult | null; supported?: Record<string, string[]>; service?: string; [k: string]: unknown };

export interface GameService {
  readonly kind: ServiceKind;
  init(): Promise<ServiceInfo>;
  balance(): Promise<number>;
  spin(req: SpinRequest): Promise<SpinResult>;
  action(req: ActionRequest): Promise<SpinResult>;
  /** 看完演出後確認；失敗不擋遊戲（下次 init 會帶回 pending） */
  ack(roundId: string): Promise<boolean>;
  /** 依局號補拿結果（斷線、分段缺漏） */
  fetch?(roundId: string): Promise<SpinResult>;
  /** 只在 dev Server 開放：強制情境 */
  readonly debug: { force(scene: unknown, o?: { bet?: number; requestId?: string }): Promise<SpinResult> } | null;
  readonly stats?: ServiceStats;
  close?(): void;
}
export type { Trace };

let rq = 0;
/** requestId：重試沿用同一個（Server 以此冪等） */
export const newRequestId = (): string => `q-${Date.now().toString(36)}-${(++rq).toString(36)}-${Math.random().toString(36).slice(2, 8)}`;

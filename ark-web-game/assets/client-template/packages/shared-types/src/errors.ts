// 錯誤碼表（HTTP 狀態碼＝WS status；ark-web-game references/wire-protocol.md §3）
export const ERROR_STATUS = {
  INVALID_BET: 400, BAD_REQUEST: 400, NOT_SUPPORTED: 400, SESSION_EXPIRED: 401, INSUFFICIENT_BALANCE: 402,
  NOT_FOUND: 404, ROUND_IN_PROGRESS: 409, PROTOCOL_MISMATCH: 426, SERVER_ERROR: 500,
} as const;
export type ServerErrorCode = keyof typeof ERROR_STATUS;
export type ClientErrorCode = 'TIMEOUT' | 'NETWORK' | 'RESULT_INCOMPLETE' | 'SCHEMA_INVALID' | 'WIRE_TOO_LARGE' | 'WIRE_BAD_HEADER' | 'WIRE_BAD_JSON' | 'MISSING_DEP';
export type ErrorCode = ServerErrorCode | ClientErrorCode | `WS_${number}` | `HTTP_${number}`;
/** 可用同一 requestId 重試的錯誤 */
export const isRetryable = (code: string): boolean => /^(NETWORK|TIMEOUT|SERVER_ERROR|HTTP_5)/.test(code);

export class ServiceError extends Error {
  constructor(public code: ErrorCode | string, message?: string, public data?: unknown) {
    super(message || code);
    this.name = 'ServiceError';
  }
  get retryable(): boolean { return isRetryable(this.code); }
}

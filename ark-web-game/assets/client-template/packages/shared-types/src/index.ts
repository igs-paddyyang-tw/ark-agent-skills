export type { SpinResultArkGameProtoStage as SpinResult } from './generated/spin-result.js';
export type { GameInfoInitArkGameProtoStageServer as GameInfo } from './generated/game-info.js';
export type { ReleaseManifestArkWebGameWgRelease as ReleaseManifest } from './generated/release-manifest.js';
export { PROTOCOL, RUNTIME_API, type Protocol } from './protocol.js';
export { ERROR_STATUS, ServiceError, isRetryable, type ErrorCode, type ServerErrorCode, type ClientErrorCode } from './errors.js';
export { validateSpinResult } from './validate.js';
export interface Trace { schema: 'proto-stage-trace/1'; info: unknown; results: import('./generated/spin-result.js').SpinResultArkGameProtoStage[] }

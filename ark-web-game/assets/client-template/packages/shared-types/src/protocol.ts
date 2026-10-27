// 本用戶端支援的協定版本（init 時送出；Server 不相容回 426 PROTOCOL_MISMATCH）。與 Stage Proto.svc.PROTOCOL 同值。
export const PROTOCOL = { result: 'proto-stage-result/1', info: 'proto-stage-info/1', wire: 'ark-wire/1' } as const;
export type Protocol = { result: string; info: string; wire: string };
export const RUNTIME_API = '1.0.0';

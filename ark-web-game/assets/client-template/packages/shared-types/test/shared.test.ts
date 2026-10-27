import { describe, expect, it } from 'vitest';
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { ERROR_STATUS, PROTOCOL, ServiceError, isRetryable, validateSpinResult } from '../src/index.js';

const root = join(__dirname, '..', '..', '..');

describe('shared-types', () => {
  it('schema 與 SOURCE.json 登記一致（兩軌共用契約）', () => {
    expect(() => execFileSync('node', [join(root, 'tools', 'schema-sync-check.mjs')])).not.toThrow();
  });
  it('PROTOCOL 與 schema 版本字串一致', () => {
    const sr = JSON.parse(readFileSync(join(root, 'schemas', 'spin-result.schema.json'), 'utf8'));
    const gi = JSON.parse(readFileSync(join(root, 'schemas', 'game-info.schema.json'), 'utf8'));
    expect(PROTOCOL.result).toBe(sr.$id);
    expect(PROTOCOL.info).toBe(gi.$id);
  });
  it('錯誤碼與重試規則', () => {
    expect(ERROR_STATUS.PROTOCOL_MISMATCH).toBe(426);
    expect(isRetryable('SERVER_ERROR') && isRetryable('NETWORK') && !isRetryable('INVALID_BET')).toBe(true);
    expect(new ServiceError('TIMEOUT').retryable).toBe(true);
  });
  it('validateSpinResult 擋帳不平與浮點金額', () => {
    const ok = { schema: 'proto-stage-result/1', roundId: 'R1', bet: 50, totalWin: 0, balanceBefore: 100, balanceAfter: 50, fx: 1, reel: { stops: [], grid: [] }, base: { win: 0, ways: [] }, feature: null };
    expect(validateSpinResult(ok)).toEqual([]);
    expect(validateSpinResult({ ...ok, balanceAfter: 51 }).length).toBeGreaterThan(0);
    expect(validateSpinResult({ ...ok, totalWin: 0.5, balanceAfter: 50.5 }).length).toBeGreaterThan(0);
  });
});

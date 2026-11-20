import { afterEach, describe, expect, it, vi } from 'vitest';
import { logAuthError } from './auth-log';

afterEach(() => vi.restoreAllMocks());

describe('logAuthError', () => {
  it('場所・名前・本文を 1 行で出す（改行は 1 つの空白にし、200 文字で切る）', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const error = new Error(`Failed to decrypt\nprivate key ${'x'.repeat(300)}`);
    error.name = 'BetterAuthError';
    logAuthError('userToken', error);
    const line = String(spy.mock.calls[0]![0]);
    expect(line.startsWith('auth: userToken failed: BetterAuthError: Failed to decrypt private key ')).toBe(true);
    expect(line).not.toContain('\n');
    expect(line.length).toBeLessThan(260);
  });

  it('Error ではない値でも落ちない（本文は出さない）', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    logAuthError('googleLoginAction', 'secret-looking-string');
    expect(spy).toHaveBeenCalledWith('auth: googleLoginAction failed: Error');
  });
});

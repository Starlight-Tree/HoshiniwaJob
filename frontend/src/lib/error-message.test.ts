import { describe, expect, it } from 'vitest';
import { ApiError } from './api';
import { messageFor } from './error-message';

describe('messageFor', () => {
  it('turns each known status into a fixed sentence', () => {
    expect(messageFor(new ApiError(401, 'x'))).toBe('メールアドレスまたはパスワードが違います');
    expect(messageFor(new ApiError(409, 'x'))).toBe('このメールアドレスは登録できません');
    expect(messageFor(new ApiError(422, 'x'))).toBe('入力内容を確認してください');
    expect(messageFor(new ApiError(429, 'x'))).toBe('ログインの試行が多すぎます。しばらくしてからもう一度お試しください');
  });

  it('falls back to a generic sentence and never shows the API text', () => {
    const text = messageFor(new ApiError(500, 'internal detail'));
    expect(text).toBe('ただいま利用できません。しばらくしてから、もう一度お試しください');
    expect(text).not.toContain('internal');
    expect(messageFor(new Error('boom'))).toBe(text);
  });
});

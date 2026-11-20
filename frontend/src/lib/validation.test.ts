import { describe, expect, it } from 'vitest';
import { validateLogin, validateName } from './validation';

describe('validateLogin', () => {
  it('パスワードの長さの決まりは見せない（空と上限だけ）', () => {
    expect(validateLogin({ email: 'a@example.com', password: 'short' })).toEqual({});
    expect(validateLogin({ email: 'a@example.com', password: '' }).password).toBe('パスワードを入力してください');
  });

  it('メールの形式を見る', () => {
    expect(validateLogin({ email: 'nope', password: 'x' }).email).toContain('形式が正しくありません');
  });
});

describe('validateName（表示名）', () => {
  it('1〜30 文字なら、エラーが無い。空と 31 文字は、表示名の欄のエラー', () => {
    expect(validateName({ display_name: 'ひかり' })).toEqual({});
    expect(validateName({ display_name: '' })).toEqual({ display_name: '表示名を入力してください' });
    expect(validateName({ display_name: 'x'.repeat(31) })).toEqual({ display_name: '表示名は 30 文字以内で入力してください' });
  });

  it('文字数はコードポイントで数える（絵文字も 1 文字）', () => {
    expect(validateName({ display_name: '😀'.repeat(30) })).toEqual({});
    expect(validateName({ display_name: '😀'.repeat(31) }).display_name).toBeDefined();
  });

  it('改行・タブなどの制御文字は使えない', () => {
    expect(validateName({ display_name: 'a\nb' }).display_name).toContain('使えない文字');
  });
});

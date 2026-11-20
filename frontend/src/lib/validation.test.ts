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

describe('validateName', () => {
  it('姓・名が 1〜50 文字なら、エラーが無い。空と 51 文字は、それぞれの欄のエラー', () => {
    expect(validateName({ last_name: '試験', first_name: '花子' })).toEqual({});
    expect(validateName({ last_name: '', first_name: 'x'.repeat(51) })).toEqual({
      last_name: '姓を入力してください',
      first_name: '名は 50 文字以内で入力してください',
    });
  });

  it('文字数はコードポイントで数える（絵文字も 1 文字）', () => {
    expect(validateName({ last_name: '😀'.repeat(50), first_name: '名' })).toEqual({});
    expect(validateName({ last_name: '😀'.repeat(51), first_name: '名' }).last_name).toBeDefined();
  });
});

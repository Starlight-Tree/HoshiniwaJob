import { describe, expect, it } from 'vitest';
import { validateLogin, validateRegister } from './validation';

const ok = { last_name: '試験', first_name: '花子', email: 'hanako@example.com', password: 'correct-horse-1' };

describe('validateRegister', () => {
  it('正しい入力ならエラーが無い', () => {
    expect(validateRegister(ok)).toEqual({});
  });

  it('メールの形式を見る', () => {
    expect(validateRegister({ ...ok, email: 'hanako@example' }).email).toContain('形式が正しくありません');
    expect(validateRegister({ ...ok, email: '' }).email).toBe('メールアドレスを入力してください');
  });

  it('パスワードは 8〜128 文字で、いまの文字数を知らせる', () => {
    expect(validateRegister({ ...ok, password: 'abc123' }).password).toBe('パスワードは 8 文字以上 128 文字以内で入力してください（いま 6 文字）');
    expect(validateRegister({ ...ok, password: 'x'.repeat(8) }).password).toBeUndefined();
    expect(validateRegister({ ...ok, password: 'x'.repeat(128) }).password).toBeUndefined();
    expect(validateRegister({ ...ok, password: 'x'.repeat(129) }).password).toContain('いま 129 文字');
  });

  it('文字数は、サロゲートペアの文字も 1 文字と数える（API と同じ）', () => {
    expect(validateRegister({ ...ok, password: '😀'.repeat(8) }).password).toBeUndefined();
  });

  it('姓・名は必須で 50 文字まで', () => {
    expect(validateRegister({ ...ok, last_name: '' }).last_name).toBe('姓を入力してください');
    expect(validateRegister({ ...ok, first_name: 'あ'.repeat(51) }).first_name).toContain('50 文字以内');
  });
});

describe('validateLogin', () => {
  it('パスワードの長さの決まりは見せない（空と上限だけ）', () => {
    expect(validateLogin({ email: 'a@example.com', password: 'short' })).toEqual({});
    expect(validateLogin({ email: 'a@example.com', password: '' }).password).toBe('パスワードを入力してください');
  });

  it('メールの形式を見る', () => {
    expect(validateLogin({ email: 'nope', password: 'x' }).email).toContain('形式が正しくありません');
  });
});

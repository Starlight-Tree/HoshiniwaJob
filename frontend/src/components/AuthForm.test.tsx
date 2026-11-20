import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { FormAction } from '../lib/form-state';
import { LoginForm } from './AuthForm';

describe('LoginForm', () => {
  it('失敗の文を、フォームの上の alert に出し、入力したメールは残す', async () => {
    const action: FormAction = vi.fn(async () => ({ error: 'メールアドレスまたはパスワードが違います', values: { email: 'a@example.com' } }));
    render(<LoginForm action={action} />);
    await userEvent.click(screen.getByRole('button', { name: 'ログイン' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('メールアドレスまたはパスワードが違います');
    expect(screen.getByLabelText('メールアドレス')).toHaveValue('a@example.com');
    expect(screen.getByLabelText('パスワード')).toHaveValue('');
  });

  it('送信中はボタンを押せず、文言が変わる（二重送信を防ぐ）', async () => {
    let release: () => void = () => {};
    const action: FormAction = () => new Promise((resolve) => (release = () => resolve({})));
    render(<LoginForm action={action} />);
    await userEvent.click(screen.getByRole('button', { name: 'ログイン' }));
    const busy = await screen.findByRole('button', { name: '送信中…' });
    expect(busy).toBeDisabled();
    release();
    await waitFor(() => expect(screen.getByRole('button', { name: 'ログイン' })).toBeEnabled());
  });

  it('パスワードは、表示・隠すの切り替えができる', async () => {
    render(<LoginForm action={vi.fn(async () => ({}))} />);
    const input = screen.getByLabelText('パスワード');
    expect(input).toHaveAttribute('type', 'password');
    await userEvent.click(screen.getByRole('button', { name: '表示' }));
    expect(input).toHaveAttribute('type', 'text');
    await userEvent.click(screen.getByRole('button', { name: '隠す' }));
    expect(input).toHaveAttribute('type', 'password');
  });
});

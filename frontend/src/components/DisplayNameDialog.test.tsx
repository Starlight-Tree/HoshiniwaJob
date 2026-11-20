import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { FormState } from '../lib/form-state';
import { DisplayNameDialog } from './DisplayNameDialog';

const action = vi.hoisted(() => vi.fn<(prev: FormState, data: FormData) => Promise<FormState>>());
vi.mock('../actions/auth', () => ({ updateNameAction: action }));

const setup = (onClose = vi.fn()) => {
  render(<DisplayNameDialog displayName="ひかり" onClose={onClose} />);
  return { onClose, dialog: screen.getByRole('dialog', { name: '表示名を変更' }) };
};

beforeEach(() => action.mockReset());

describe('DisplayNameDialog', () => {
  it('いまの表示名を入れて開き、欄にフォーカスする。説明文・姓・名の欄は無い', () => {
    setup();
    expect(screen.getByLabelText('表示名')).toHaveValue('ひかり');
    expect(screen.getByLabelText('表示名')).toHaveFocus();
    expect(screen.queryByLabelText('姓')).not.toBeInTheDocument();
    expect(screen.queryByText(/自分にだけ表示/)).not.toBeInTheDocument();
  });

  it('表示名が無い人は、空の欄で開く', () => {
    render(<DisplayNameDialog displayName={null} onClose={vi.fn()} />);
    expect(screen.getByLabelText('表示名')).toHaveValue('');
  });

  it('保存すると、入力した値を渡し、保存できたら閉じる', async () => {
    action.mockResolvedValue({ saved: true, values: { display_name: '新しい名前' } });
    const { onClose } = setup();
    await userEvent.clear(screen.getByLabelText('表示名'));
    await userEvent.type(screen.getByLabelText('表示名'), '新しい名前');
    await userEvent.click(screen.getByRole('button', { name: '保存' }));
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
    const data = action.mock.calls[0]![1];
    expect(data.get('display_name')).toBe('新しい名前');
  });

  it('失敗したら、閉じずに、固定の文と入力した値を残す', async () => {
    action.mockResolvedValue({ error: 'ただいま利用できません。しばらくしてから、もう一度お試しください', values: { display_name: '新しい名前' } });
    const { onClose } = setup();
    await userEvent.click(screen.getByRole('button', { name: '保存' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('ただいま利用できません');
    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByLabelText('表示名')).toHaveValue('新しい名前');
  });

  it('入力の誤りは、欄の下に出して、閉じない', async () => {
    action.mockResolvedValue({ fieldErrors: { display_name: '表示名を入力してください' }, values: { display_name: '' } });
    const { onClose } = setup();
    await userEvent.click(screen.getByRole('button', { name: '保存' }));
    expect(await screen.findByText('表示名を入力してください')).toBeInTheDocument();
    expect(onClose).not.toHaveBeenCalled();
  });

  it('キャンセルで閉じる（保存しない）。外側の押下では閉じない', async () => {
    const { onClose, dialog } = setup();
    await userEvent.click(dialog);
    expect(onClose).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole('button', { name: 'キャンセル' }));
    expect(action).not.toHaveBeenCalled();
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });
});

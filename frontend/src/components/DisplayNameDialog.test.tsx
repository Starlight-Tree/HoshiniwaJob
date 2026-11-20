import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { FormState } from '../lib/form-state';
import { DisplayNameDialog } from './DisplayNameDialog';

const action = vi.hoisted(() => vi.fn<(prev: FormState, data: FormData) => Promise<FormState>>());
vi.mock('../actions/auth', () => ({ updateNameAction: action }));

const setup = (onClose = vi.fn()) => {
  render(<DisplayNameDialog lastName="試験" firstName="花子" onClose={onClose} />);
  return { onClose, dialog: screen.getByRole('dialog', { name: '表示名を変更' }) };
};

beforeEach(() => action.mockReset());

describe('DisplayNameDialog', () => {
  it('いまの姓・名を入れて開き、先頭の欄にフォーカスする', () => {
    setup();
    expect(screen.getByLabelText('姓')).toHaveValue('試験');
    expect(screen.getByLabelText('名')).toHaveValue('花子');
    expect(screen.getByLabelText('姓')).toHaveFocus();
  });

  it('保存すると、入力した値を渡し、保存できたら閉じる', async () => {
    action.mockResolvedValue({ saved: true, values: { last_name: '新姓', first_name: '新名' } });
    const { onClose } = setup();
    await userEvent.clear(screen.getByLabelText('姓'));
    await userEvent.type(screen.getByLabelText('姓'), '新姓');
    await userEvent.clear(screen.getByLabelText('名'));
    await userEvent.type(screen.getByLabelText('名'), '新名');
    await userEvent.click(screen.getByRole('button', { name: '保存' }));
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
    const data = action.mock.calls[0]![1];
    expect([data.get('last_name'), data.get('first_name')]).toEqual(['新姓', '新名']);
  });

  it('失敗したら、閉じずに、固定の文と入力した値を残す', async () => {
    action.mockResolvedValue({ error: 'ただいま利用できません。しばらくしてから、もう一度お試しください', values: { last_name: '新姓', first_name: '新名' } });
    const { onClose } = setup();
    await userEvent.click(screen.getByRole('button', { name: '保存' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('ただいま利用できません');
    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByLabelText('姓')).toHaveValue('新姓');
  });

  it('入力の誤りは、欄の下に出して、閉じない', async () => {
    action.mockResolvedValue({ fieldErrors: { last_name: '姓を入力してください' }, values: { last_name: '', first_name: '花子' } });
    const { onClose } = setup();
    await userEvent.click(screen.getByRole('button', { name: '保存' }));
    expect(await screen.findByText('姓を入力してください')).toBeInTheDocument();
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

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it } from 'vitest';
import { RegisteredNotice } from './RegisteredNotice';

afterEach(() => {
  document.cookie = 'hj_registered=; Max-Age=0; path=/';
});

describe('RegisteredNotice', () => {
  it('印が無ければ何も出さない', () => {
    const { container } = render(<RegisteredNotice />);
    expect(container).toBeEmptyDOMElement();
  });

  it('印があれば出し、その場で印を消す。×で閉じられ、描画し直しても出ない', async () => {
    document.cookie = 'hj_registered=1; path=/';
    const { unmount } = render(<RegisteredNotice />);
    expect(await screen.findByRole('status')).toHaveTextContent('会員登録が完了しました');
    expect(document.cookie).not.toContain('hj_registered');

    await userEvent.click(screen.getByRole('button', { name: 'メッセージを閉じる' }));
    expect(screen.queryByRole('status')).not.toBeInTheDocument();

    unmount();
    const again = render(<RegisteredNotice />);
    expect(again.container).toBeEmptyDOMElement();
  });
});

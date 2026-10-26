import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { AccountMenu } from './AccountMenu';

const setup = () => render(<AccountMenu name="試験 花子" email="hanako@example.com" logout={vi.fn(async () => {})} />);

describe('AccountMenu', () => {
  it('はじめは閉じていて、押すと名前・メール・ログアウトが出る', async () => {
    setup();
    const button = screen.getByRole('button', { name: /試験 花子/ });
    expect(button).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByText('hanako@example.com')).not.toBeInTheDocument();

    await userEvent.click(button);
    expect(button).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByText('試験 花子 さん')).toBeInTheDocument();
    expect(screen.getByText('hanako@example.com')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'ログアウト' })).toBeInTheDocument();
  });

  it('Esc と、外を押したときに閉じる', async () => {
    setup();
    const button = screen.getByRole('button', { name: /試験 花子/ });
    await userEvent.click(button);
    await userEvent.keyboard('{Escape}');
    expect(button).toHaveAttribute('aria-expanded', 'false');
    expect(button).toHaveFocus();

    await userEvent.click(button);
    await userEvent.click(document.body);
    expect(button).toHaveAttribute('aria-expanded', 'false');
  });

  it('敬称を変えられる（園は「御中」）', async () => {
    render(<AccountMenu name="環軌道植物公社" email="garden@example.com" honorific="御中" logout={vi.fn(async () => {})} />);
    await userEvent.click(screen.getByRole('button', { name: /環軌道植物公社/ }));
    expect(screen.getByText('環軌道植物公社 御中')).toBeInTheDocument();
    expect(screen.queryByText(/さん/)).not.toBeInTheDocument();
  });
});

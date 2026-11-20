import { act, render, renderHook, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PanelProvider, PanelSlot, usePanel } from './PanelProvider';

const nav = vi.hoisted(() => ({ pathname: '/', search: '' }));
vi.mock('next/navigation', () => ({
  usePathname: () => nav.pathname,
  useSearchParams: () => new URLSearchParams(nav.search),
}));

beforeEach(() => {
  nav.pathname = '/';
  nav.search = '';
});

describe('PanelSlot（URL が詳細のときだけ、パネルのスロットを出す）', () => {
  it.each(['/recruits/7', '/recruits/123'])('%s では出す', (pathname) => {
    nav.pathname = pathname;
    render(<PanelSlot>パネル</PanelSlot>);
    expect(screen.getByText('パネル')).toBeInTheDocument();
  });

  it.each(['/', '/diagnosis', '/recruits', '/recruits/abc', '/login'])('%s では出さない（前の状態が残っていても、居残らせない）', (pathname) => {
    nav.pathname = pathname;
    render(<PanelSlot>パネル</PanelSlot>);
    expect(screen.queryByText('パネル')).toBeNull();
  });
});

describe('PanelProvider', () => {
  const wrapper = ({ children }: { children: ReactNode }) => <PanelProvider>{children}</PanelProvider>;

  it('一覧のパスとクエリを覚え、詳細（/recruits/ID）では覚え直さない。覚えていなければ /', () => {
    nav.pathname = '/diagnosis';
    nav.search = 'area=2';
    const { result, rerender } = renderHook(() => usePanel(), { wrapper });
    expect(result.current.listUrl()).toBe('/diagnosis?area=2');
    nav.pathname = '/recruits/5';
    nav.search = 'area=2';
    rerender();
    expect(result.current.listUrl()).toBe('/diagnosis?area=2');
  });

  it('詳細から離れると、拡大を戻す', () => {
    nav.pathname = '/recruits/5';
    const { result, rerender } = renderHook(() => usePanel(), { wrapper });
    expect(result.current.listUrl()).toBe('/');
    // 拡大（state の更新は act の中で）
    act(() => result.current.setExpanded(true));
    expect(result.current.expanded).toBe(true);
    nav.pathname = '/';
    rerender();
    expect(result.current.expanded).toBe(false);
  });

  it('Provider の外で usePanel を使うと、はっきり失敗する', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    expect(() => renderHook(() => usePanel())).toThrow('PanelProvider');
  });
});

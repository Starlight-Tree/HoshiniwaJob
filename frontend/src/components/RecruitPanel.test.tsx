import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { PanelProvider } from './PanelProvider';
import { RecruitPanel } from './RecruitPanel';

const nav = vi.hoisted(() => ({ pathname: '/recruits/7', search: '', push: vi.fn() }));
vi.mock('next/navigation', () => ({
  usePathname: () => nav.pathname,
  useSearchParams: () => new URLSearchParams(nav.search),
  useRouter: () => ({ push: nav.push }),
}));

// 画面の幅（matchMedia）の差し替え。resize で、幅が変わったことを購読者へ知らせる
let wide = true;
const listeners = new Set<() => void>();
function stubMatchMedia() {
  vi.stubGlobal('matchMedia', (query: string) => ({
    matches: query === '(min-width: 1280px)' ? wide : false,
    media: query,
    addEventListener: (_type: string, fn: () => void) => listeners.add(fn),
    removeEventListener: (_type: string, fn: () => void) => listeners.delete(fn),
  }));
}
function resizeTo(next: boolean) {
  wide = next;
  act(() => {
    for (const fn of [...listeners]) fn();
  });
}

function Detail() {
  return (
    <>
      <h2 tabIndex={-1} data-panel-heading="">
        温室の見習い
      </h2>
      <p>本文</p>
    </>
  );
}

function panel(props: { loading?: boolean } = {}) {
  return (
    <PanelProvider>
      <RecruitPanel {...props}>
        <Detail />
      </RecruitPanel>
    </PanelProvider>
  );
}

// 背後（本文とサイドパネル）と、押したカードの代わり
function mountPage() {
  document.body.insertAdjacentHTML(
    'beforeend',
    `<div id="page"><aside class="app-sidebar"><a href="/">戻る</a></aside><div class="app-main"><div data-recruit-id="7"><h2><a id="card-7" href="/recruits/7">温室の見習い</a></h2></div></div></div>`,
  );
}

beforeEach(() => {
  nav.pathname = '/recruits/7';
  nav.search = '';
  nav.push.mockClear();
  wide = true;
  listeners.clear();
  stubMatchMedia();
  mountPage();
});
afterEach(() => {
  document.getElementById('page')?.remove();
  vi.unstubAllGlobals();
});

describe('RecruitPanel（広い画面）', () => {
  it('非モーダルの <aside>（名前「求人の詳細」）。背後は操作できる（inert にしない）', () => {
    render(panel());
    const aside = screen.getByRole('complementary', { name: '求人の詳細' });
    expect(aside).not.toHaveAttribute('role');
    expect(aside).not.toHaveAttribute('aria-modal');
    expect(aside).toHaveAttribute('data-mode', 'panel');
    expect(document.querySelector('.app-main')).not.toHaveAttribute('inert');
    expect(document.querySelector('.app-sidebar')).not.toHaveAttribute('inert');
  });

  it('「ページで開く」は、Link ではなく通常のアンカー（クエリも引き継ぐ）', () => {
    nav.search = 'area=3&page=2';
    render(panel());
    const link = screen.getByRole('link', { name: 'ページで開く' });
    expect(link.tagName).toBe('A');
    expect(link).toHaveAttribute('href', '/recruits/7?area=3&page=2');
    // 横取り（preventDefault）しない = ブラウザーの通常の移動（全ページ）に任せる。React の処理のあと（document）で見て、jsdom が移動しようとしないよう、ここで止める
    let prevented = true;
    const probe = (event: MouseEvent) => {
      prevented = event.defaultPrevented;
      event.preventDefault();
    };
    document.addEventListener('click', probe);
    fireEvent.click(link);
    document.removeEventListener('click', probe);
    expect(prevented).toBe(false);
  });

  it('拡大ボタン: 名前は「拡大」「縮小」、aria-pressed と data-expanded が切り替わり、拡大中は背後（本文とサイドパネル）が inert', () => {
    render(panel());
    const aside = screen.getByRole('complementary', { name: '求人の詳細' });
    const button = screen.getByRole('button', { name: '拡大' });
    expect(button).toHaveAttribute('aria-pressed', 'false');
    expect(aside).not.toHaveAttribute('data-expanded');

    fireEvent.click(button);
    const shrink = screen.getByRole('button', { name: '縮小' });
    expect(shrink).toHaveAttribute('aria-pressed', 'true');
    expect(aside).toHaveAttribute('data-expanded', 'true');
    expect(document.querySelector('.app-main')).toHaveAttribute('inert');
    expect(document.querySelector('.app-sidebar')).toHaveAttribute('inert');

    fireEvent.click(shrink);
    expect(screen.getByRole('button', { name: '拡大' })).toHaveAttribute('aria-pressed', 'false');
    expect(aside).not.toHaveAttribute('data-expanded');
    expect(document.querySelector('.app-main')).not.toHaveAttribute('inert');
    expect(document.querySelector('.app-sidebar')).not.toHaveAttribute('inert');
  });

  it('閉じるボタン: 一覧の URL（フィルター・ページを含む）へ push する。覚えていなければ /。押した直後にパネルは見えなくなる', () => {
    render(panel());
    fireEvent.click(screen.getByRole('button', { name: '閉じる' }));
    expect(nav.push).toHaveBeenCalledTimes(1);
    expect(nav.push).toHaveBeenCalledWith('/', { scroll: false });
    // 応答を待たず、すぐ隠す
    expect(document.querySelector('aside.recruit-panel')).toHaveAttribute('hidden');
  });

  it('閉じるときは、直前に見ていた一覧の URL へ戻る（/recruits/ 以外のパスとクエリを覚えている）。拡大も戻る', () => {
    nav.pathname = '/';
    nav.search = 'area=3&page=2';
    const { rerender } = render(panel());
    // 一覧のカードを押して、詳細へ移る
    nav.pathname = '/recruits/7';
    nav.search = 'area=3&page=2';
    rerender(panel());
    fireEvent.click(screen.getByRole('button', { name: '拡大' }));
    fireEvent.click(screen.getByRole('button', { name: '閉じる' }));
    expect(nav.push).toHaveBeenCalledWith('/?area=3&page=2', { scroll: false });
    expect(document.querySelector('.app-main')).not.toHaveAttribute('inert');
  });

  it('診断の結果から開いたときも、診断の URL へ戻る', () => {
    nav.pathname = '/diagnosis';
    nav.search = 'work=2&place=1';
    const { rerender } = render(panel());
    nav.pathname = '/recruits/7';
    nav.search = '';
    rerender(panel());
    fireEvent.click(screen.getByRole('button', { name: '閉じる' }));
    expect(nav.push).toHaveBeenCalledWith('/diagnosis?work=2&place=1', { scroll: false });
  });

  it('Esc で閉じる。しぼり込みの一覧・メニュー・ダイアログの中の Esc は、そちらに任せて閉じない', () => {
    render(panel());
    document.body.insertAdjacentHTML('beforeend', '<details id="facet" class="facet" open><summary>職種</summary><input id="in" /></details>');
    fireEvent.keyDown(document.getElementById('in') as HTMLElement, { key: 'Escape' });
    expect(nav.push).not.toHaveBeenCalled();
    document.getElementById('facet')?.remove();

    fireEvent.keyDown(document.body, { key: 'Enter' });
    expect(nav.push).not.toHaveBeenCalled();
    fireEvent.keyDown(document.body, { key: 'Escape' });
    expect(nav.push).toHaveBeenCalledTimes(1);
    // 二重に閉じない
    fireEvent.keyDown(document.body, { key: 'Escape' });
    expect(nav.push).toHaveBeenCalledTimes(1);
  });

  it('拡大中の Esc も、閉じる（拡大も戻る）', () => {
    render(panel());
    fireEvent.click(screen.getByRole('button', { name: '拡大' }));
    fireEvent.keyDown(document.body, { key: 'Escape' });
    expect(nav.push).toHaveBeenCalledTimes(1);
    expect(document.querySelector('.app-main')).not.toHaveAttribute('inert');
  });
});

describe('RecruitPanel のフォーカス', () => {
  it('詳細が届いて開いたら、見出し（tabIndex=-1）へフォーカスを移す', () => {
    render(panel());
    expect(within(screen.getByRole('complementary', { name: '求人の詳細' })).getByRole('heading', { name: '温室の見習い' })).toHaveFocus();
  });

  it('骨格（loading）のあいだは、フォーカスを動かさず、aria-busy を付ける。ボタンは使える', () => {
    const { container } = render(
      <PanelProvider>
        <RecruitPanel loading>
          <p>骨格</p>
        </RecruitPanel>
      </PanelProvider>,
    );
    expect(document.activeElement).toBe(document.body);
    expect(container.querySelector('aside')).toHaveAttribute('aria-busy', 'true');
    expect(screen.getByRole('button', { name: '閉じる' })).toBeEnabled();
  });

  it('閉じたら、押したカードの題名のリンクへフォーカスを戻す（拡大中でも。inert を外してから）', () => {
    render(panel());
    fireEvent.click(screen.getByRole('button', { name: '拡大' }));
    fireEvent.click(screen.getByRole('button', { name: '閉じる' }));
    expect(document.getElementById('card-7')).toHaveFocus();
  });

  it('Esc で閉じたときも、カードのリンクへ戻す', () => {
    render(panel());
    fireEvent.keyDown(document.activeElement ?? document.body, { key: 'Escape' });
    expect(document.getElementById('card-7')).toHaveFocus();
  });
});

describe('RecruitPanel（狭い画面のシート）', () => {
  beforeEach(() => {
    wide = false;
  });

  it('role="dialog" aria-modal="true" で、背後（本文とサイドパネル）を inert にする。拡大ボタンは出さない（もともと全画面）', () => {
    render(panel());
    const dialog = screen.getByRole('dialog', { name: '求人の詳細' });
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(dialog).toHaveAttribute('data-mode', 'sheet');
    expect(document.querySelector('.app-main')).toHaveAttribute('inert');
    expect(document.querySelector('.app-sidebar')).toHaveAttribute('inert');
    expect(screen.queryByRole('button', { name: '拡大' })).toBeNull();
    expect(screen.getByRole('button', { name: '閉じる' })).toBeInTheDocument();
  });

  it('アンマウント（別の画面へ移る）で、inert を外す', () => {
    const { unmount } = render(panel());
    expect(document.querySelector('.app-main')).toHaveAttribute('inert');
    unmount();
    expect(document.querySelector('.app-main')).not.toHaveAttribute('inert');
  });

  it('シートで閉じても、カードのリンクへフォーカスが戻る', () => {
    render(panel());
    fireEvent.click(screen.getByRole('button', { name: '閉じる' }));
    expect(nav.push).toHaveBeenCalledWith('/', { scroll: false });
    expect(document.getElementById('card-7')).toHaveFocus();
  });
});

describe('RecruitPanel の画面の大きさの変化（開いたまま）', () => {
  it('広い→狭い→広い: シートとパネルを切り替え、inert・拡大の状態が壊れない', () => {
    render(panel());
    fireEvent.click(screen.getByRole('button', { name: '拡大' }));
    expect(screen.getByRole('complementary', { name: '求人の詳細' })).toHaveAttribute('data-expanded', 'true');

    resizeTo(false);
    const dialog = screen.getByRole('dialog', { name: '求人の詳細' });
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    // 全画面のシートでは、拡大の表示は使わない（状態は覚えておく）
    expect(dialog).not.toHaveAttribute('data-expanded');
    expect(document.querySelector('.app-main')).toHaveAttribute('inert');

    resizeTo(true);
    const aside = screen.getByRole('complementary', { name: '求人の詳細' });
    expect(aside).toHaveAttribute('data-expanded', 'true');
    expect(screen.getByRole('button', { name: '縮小' })).toHaveAttribute('aria-pressed', 'true');
    expect(document.querySelector('.app-main')).toHaveAttribute('inert');

    fireEvent.click(screen.getByRole('button', { name: '縮小' }));
    expect(document.querySelector('.app-main')).not.toHaveAttribute('inert');
  });

  it('拡大していない広い画面→狭い画面: シートになり、背後が inert。広い画面に戻すと外れる', () => {
    render(panel());
    expect(document.querySelector('.app-main')).not.toHaveAttribute('inert');
    resizeTo(false);
    expect(document.querySelector('.app-main')).toHaveAttribute('inert');
    resizeTo(true);
    expect(document.querySelector('.app-main')).not.toHaveAttribute('inert');
  });
});

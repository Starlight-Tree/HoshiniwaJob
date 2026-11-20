'use client';

import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useRef, useState, useSyncExternalStore } from 'react';
import type { ReactNode } from 'react';
import { CloseIcon, CollapseIcon, ExpandIcon, OpenPageIcon } from './panelIcons';
import { RECRUIT_PATH, usePanel } from './PanelProvider';

// パネルを一覧の右に並べる幅（globals.css の @media (min-width: 1280px) と同じ値）。これより狭い画面は、全画面のシート
const WIDE = '(min-width: 1280px)';

function subscribeWide(onChange: () => void): () => void {
  if (typeof window.matchMedia !== 'function') return () => {};
  const query = window.matchMedia(WIDE);
  query.addEventListener('change', onChange);
  return () => query.removeEventListener('change', onChange);
}

function isWide(): boolean {
  return typeof window.matchMedia === 'function' && window.matchMedia(WIDE).matches;
}

// パネルが開くのは、画面の中の操作（一覧のカードを押す）のあと。サーバーでは描画しないので、サーバー側の値は仮のもの
function useWide(): boolean {
  return useSyncExternalStore(subscribeWide, isWide, () => false);
}

// パネルが開いている間、操作と読み上げから外す所。拡大中と、シートの間は、背後（本文とサイドパネル）が対象
const BEHIND = '.app-main, .app-sidebar';

type Props = {
  children: ReactNode;
  /** 骨格（loading.tsx）として出すとき。詳細が届くまでの間で、フォーカスは動かさない。 */
  loading?: boolean;
};

/**
 * 一覧に重ねる求人の詳細パネルの殻（ヘッダー・フォーカス・Esc・背後の inert・シートとの切り替え）。中身は Server Component の RecruitDetailView を、children で受ける。
 * - 広い画面（1280px 以上）: 一覧の右に並ぶ、非モーダルの <aside>（一覧も操作できる）。「拡大」で、同じ要素のまま、サイドパネルの右を覆う（CSS だけ。中身は作り直さない）。
 * - 狭い画面: 全画面のシート（role="dialog" aria-modal="true"）。画面の大きさを変えても、開いたまま、役割と inert が切り替わる。
 * - 詳細が届いて開いたら、見出しへフォーカスを移す。閉じる（ボタン・Esc）と、押したカードの題名のリンクへ戻す。
 * - 「ページで開く」は、Link ではなく通常の <a>。Link だと、同じ URL への移動を、また横取り（パネルで開き直し）してしまうため。
 * - 閉じるときは、直前の一覧の URL（フィルター・ページを含む）へ移す。URL が /recruits/ID のままだと、一覧へ戻れない。
 */
export function RecruitPanel({ children, loading = false }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const search = useSearchParams().toString();
  const { expanded, setExpanded, listUrl } = usePanel();
  const wide = useWide();
  const [closing, setClosing] = useState(false);
  const ref = useRef<HTMLElement>(null);

  const sheet = !wide;
  // 広い画面の拡大と、狭い画面のシートは、背後を操作させない
  const modal = (sheet || expanded) && !closing;
  const id = RECRUIT_PATH.exec(pathname)?.[1];
  const pageHref = search ? `${pathname}?${search}` : pathname;

  const close = () => {
    if (closing) return;
    // 一覧へ戻る移動は、サーバーの応答を待つ。その間も、パネルはすぐ見えなくする
    setClosing(true);
    setExpanded(false);
    router.push(listUrl(), { scroll: false });
  };
  // Esc の受け口は、画面に 1 つだけ置いた listener から、いつも最新の close を呼ぶ
  const closeRef = useRef(close);
  closeRef.current = close;

  // 背後の inert。先に宣言して、閉じるときの後始末（inert を外す）が、下のフォーカスを戻す処理より先に走るようにする（inert の要素にはフォーカスできない）
  useEffect(() => {
    if (!modal) return;
    const targets = [...document.querySelectorAll(BEHIND)];
    for (const el of targets) el.setAttribute('inert', '');
    return () => {
      for (const el of targets) el.removeAttribute('inert');
    };
  }, [modal]);

  // 詳細が届いて開いたら、見出しへ。骨格のときは動かさない（骨格から詳細への入れ替わりで、この部品は作り直される）
  useEffect(() => {
    if (loading) return;
    ref.current?.querySelector<HTMLElement>('[data-panel-heading]')?.focus({ preventScroll: true });
  }, [loading]);

  // 閉じたら、押したカードの題名のリンクへフォーカスを戻す（パネルが消えると、フォーカスが行方不明になるため）
  useEffect(() => {
    if (!closing || id === undefined) return;
    document.querySelector<HTMLElement>(`[data-recruit-id="${id}"] h2 a`)?.focus();
  }, [closing, id]);

  // Esc で閉じる。一覧のしぼり込みの一覧・アカウントのメニュー・ダイアログが先に受けるべき Esc（その中にフォーカスがあるとき）は、何もしない
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape' || event.defaultPrevented) return;
      if (event.target instanceof Element && event.target.closest('details, [role="menu"], dialog')) return;
      event.preventDefault();
      closeRef.current();
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, []);

  return (
    <aside
      ref={ref}
      className="recruit-panel"
      aria-label="求人の詳細"
      role={sheet ? 'dialog' : undefined}
      aria-modal={sheet ? true : undefined}
      aria-busy={loading || undefined}
      data-mode={sheet ? 'sheet' : 'panel'}
      data-expanded={wide && expanded ? 'true' : undefined}
      data-loading={loading ? 'true' : undefined}
      hidden={closing}
    >
      <div className="recruit-panel-surface">
        <header className="recruit-panel-head">
          <a className="recruit-panel-page" href={pageHref}>
            <OpenPageIcon />
            ページで開く
          </a>
          <span className="recruit-panel-tools">
            {/* 拡大は、広い画面だけ（シートは、もともと全画面）。同じ要素のまま、CSS だけで広がる（DocuNavi の資料パネルと同じ） */}
            {wide ? (
              <button
                type="button"
                className="recruit-panel-btn"
                aria-label={expanded ? '縮小' : '拡大'}
                title={expanded ? '縮小' : '拡大'}
                aria-pressed={expanded}
                onClick={() => setExpanded(!expanded)}
              >
                {expanded ? <CollapseIcon /> : <ExpandIcon />}
              </button>
            ) : null}
            <button type="button" className="recruit-panel-btn" aria-label="閉じる" title="閉じる" onClick={close}>
              <CloseIcon />
            </button>
          </span>
        </header>
        <div className="recruit-panel-body detail">{children}</div>
      </div>
    </aside>
  );
}

'use client';

import { usePathname, useSearchParams } from 'next/navigation';
import { Suspense, createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';

/** 求人の詳細は /recruits/ID。パネルが開いている間の URL。 */
export const RECRUIT_PATH = /^\/recruits\/(\d+)/;

type PanelState = {
  /** パネルの拡大。骨格（loading.tsx）から詳細（page.tsx）へ入れ替わるとパネルの部品は作り直されるので、拡大の状態はここ（作り直されない所）に置く。 */
  expanded: boolean;
  setExpanded: (value: boolean) => void;
  /** 閉じたときに戻る、直前の一覧の URL（パスとクエリ。フィルター・ページを含む）。なければ /。 */
  listUrl: () => string;
};

const PanelContext = createContext<PanelState | null>(null);

export function usePanel(): PanelState {
  const state = useContext(PanelContext);
  if (state === null) throw new Error('PanelProvider の中で使ってください');
  return state;
}

/**
 * 一覧の URL を覚え、パネルの拡大の状態を持つ（(site)/layout.tsx に置く小さなクライアント部品）。
 * 詳細パネルは URL が /recruits/ID になるので、閉じるときに「どの一覧へ戻るか」は URL からは分からない。
 * /recruits/ 以外のパスとクエリ（求人の一覧・診断の結果など）を、画面を移るたびに覚えておく。
 */
export function PanelProvider({ children }: { children: ReactNode }) {
  const [expanded, setExpanded] = useState(false);
  const listRef = useRef('/');
  const remember = useCallback((url: string) => {
    listRef.current = url;
  }, []);
  const value = useMemo<PanelState>(() => ({ expanded, setExpanded, listUrl: () => listRef.current }), [expanded]);
  return (
    <PanelContext.Provider value={value}>
      {children}
      {/* 見せるものは無い。useSearchParams を使うので、Suspense で囲む（静的な描画のときの CSR への切り替えを、この部品だけに閉じ込める） */}
      <Suspense fallback={null}>
        <ListUrlTracker remember={remember} />
      </Suspense>
    </PanelContext.Provider>
  );
}

function ListUrlTracker({ remember }: { remember: (url: string) => void }) {
  const pathname = usePathname();
  const search = useSearchParams().toString();
  const { setExpanded } = usePanel();
  useEffect(() => {
    // 詳細（/recruits/ID）は覚えない。直前の一覧のまま
    if (RECRUIT_PATH.test(pathname)) return;
    remember(search ? `${pathname}?${search}` : pathname);
    // 詳細から離れたら（閉じる・戻る・フィルターを押す・ほかの画面へ移る）、拡大も戻す。次に開くときは、通常の幅から
    setExpanded(false);
  }, [pathname, search, remember, setExpanded]);
  return null;
}

/**
 * パネルのスロット（@panel）を、URL が /recruits/ID のときだけ出す。
 * 並行ルートは、移り先に合う画面がないスロットを、前の状態のまま残す（詳細から診断へ移っても、パネルが残る）。公式の文書は、スロットに
 * [...catchAll]/page.tsx（null を返す）を置いて空にする方法を示すが、この Next.js（16.4）の厳密な経路の照合では、(site) の中のスロットの
 * catch-all が、同じ階層の (auth)・garden のページ（/login・/garden…）を「完全な経路のないページ」にして 404 にしてしまう（next dev で実測）。
 * そこで、空にする役を、URL を見るこの部品に任せる。新しい画面を (site) に足しても、パネルが居残らない。
 */
export function PanelSlot({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return RECRUIT_PATH.test(pathname) ? children : null;
}

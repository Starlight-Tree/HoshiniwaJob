'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useRef, useState, useTransition, type ReactNode } from 'react';
import { hrefFor, KINDS, type Kind, type Selection } from '../lib/search';
import type { Code, Facets, Master } from '../lib/types';

type Props = { master: Master; facets: Facets; selection: Selection };

const FACET_KEY: Record<Kind, keyof Omit<Facets, 'total'>> = {
  employment: 'employments',
  area: 'areas',
  station: 'stations',
  occupation: 'occupations',
};

function counts(facets: Facets, kind: Kind): Map<number, number> {
  return new Map(facets[FACET_KEY[kind]].map((f) => [f.code, f.count]));
}

// サーバーから来た選択（URL）と同じかを見分けるための鍵
function keyOf(sel: Selection): string {
  return KINDS.map((k) => `${k}:${sel[k].join(',')}`).join('|');
}

/**
 * 「ラベル 値 ▾」のチップ（2 つ以上選ぶと「ほか N」を添える）と、その真下に開く選択肢の一覧（DocuNavi の資料一覧の絞り込みと同じ形。複数選べる点だけ違う）。
 * 開閉は、ブラウザー標準の <details> に任せる（JavaScript が無くても開き、チェックを入れて送れる）。
 * 外を押す・Esc・別のチップを開く、で閉じるのは、FilterForm の側が受ける。
 */
function Facet({ label, names, wide, children }: { label: string; names: string[]; wide?: boolean; children: ReactNode }) {
  const active = names.length > 0;
  return (
    <details className="facet" data-active={active}>
      <summary className="facet-summary" title={active ? `${label}：${names.join('、')}` : undefined}>
        <span className="facet-label">{label}</span>
        {/* 選んでいなければ「すべて」、1 つ以上ならその先頭の名前（長ければ「…」で省略）。2 つ目以降は、省略されないよう、件数を別に出す */}
        <span className="facet-value">{names[0] ?? 'すべて'}</span>
        {names.length > 1 ? <span className="facet-more">ほか{names.length - 1}</span> : null}
        <span className="facet-caret" aria-hidden="true">
          ▾
        </span>
      </summary>
      <div className={`facet-panel${wide ? ' facet-panel-wide' : ''}`}>{children}</div>
    </details>
  );
}

// 職種の区分ごとの折りたたみ。選んだ職種がある区分は、最初から開いておく。
// 選びが 0 から増えたとき（戻る操作など）は開く。ユーザーが閉じた区分は、選びが増えない限り閉じたままにする。
function OccupationGroup({
  group,
  picked,
  renderOption,
}: {
  group: Master['occupations'][number];
  picked: number;
  renderOption: (item: Code) => ReactNode;
}) {
  const [open, setOpen] = useState(picked > 0);
  const [prevPicked, setPrevPicked] = useState(picked);
  if (picked !== prevPicked) {
    setPrevPicked(picked);
    if (prevPicked === 0 && picked > 0) setOpen(true);
  }
  return (
    <details open={open} onToggle={(e) => setOpen(e.currentTarget.open)}>
      <summary>
        {group.category}
        {picked > 0 ? <span className="picked">{picked} 件選択中</span> : null}
      </summary>
      {group.items.map((item) => renderOption(item))}
    </details>
  );
}

export function FilterForm({ master, facets, selection }: Props) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const formRef = useRef<HTMLFormElement>(null);
  // JavaScript が動いているあいだは、チェックを入れた時点で絞り込むので、送信ボタンは隠す（JavaScript が無いときだけ、ボタンで送る）
  const [enhanced, setEnhanced] = useState(false);
  useEffect(() => setEnhanced(true), []);
  // 画面の選択は、チェックを入れた瞬間に変える（サーバーの再描画を待たない）。
  // URL が別の経路（チップの ✕、クリア、戻る）で変わったときは、サーバーの選択に合わせ直す。
  const [chosen, setChosen] = useState(selection);
  const [seen, setSeen] = useState(keyOf(selection));
  if (keyOf(selection) !== seen) {
    setSeen(keyOf(selection));
    setChosen(selection);
  }

  // チップの一覧を、外を押す・フォーカスが外へ出る・Esc・別のチップを開く・画面の幅が変わる、で閉じる。Esc のときは、開いていたチップへフォーカスを戻す。
  // 開いたとき、一覧が画面の右へはみ出すなら、チップの右端にそろえて開く（チップの位置は、幅によって変わる）
  useEffect(() => {
    const form = formRef.current;
    if (!form) return;
    const menus = () => [...form.querySelectorAll<HTMLDetailsElement>('details.facet')];
    const closeAll = () => {
      for (const d of menus()) d.open = false;
    };
    const onPointer = (event: MouseEvent) => {
      for (const d of menus()) if (d.open && !d.contains(event.target as Node)) d.open = false;
    };
    const onFocusOut = (event: FocusEvent) => {
      const d = (event.target as Element).closest<HTMLDetailsElement>('details.facet');
      const next = event.relatedTarget as Node | null;
      // 移り先が分かるとき（Tab・クリックで別の要素へ）だけ。ウィンドウを離れたとき（移り先なし）は、開いたままにする
      if (d?.open && next && !d.contains(next)) d.open = false;
    };
    const onKey = (event: KeyboardEvent) => {
      // アカウントのメニューなど、ほかの Esc の処理が先に受けたときは、何もしない（フォーカスを奪わない）
      if (event.key !== 'Escape' || event.defaultPrevented) return;
      const opened = menus().find((d) => d.open);
      if (!opened) return;
      opened.open = false;
      opened.querySelector<HTMLElement>('summary')?.focus();
    };
    const onToggle = (event: Event) => {
      const target = event.target as HTMLElement;
      if (!(target instanceof HTMLDetailsElement) || !target.classList.contains('facet') || !target.open) return;
      for (const d of menus()) if (d !== target && d.open) d.open = false;
      delete target.dataset.align;
      const panel = target.querySelector<HTMLElement>('.facet-panel');
      if (panel && panel.getBoundingClientRect().right > document.documentElement.clientWidth - 8) target.dataset.align = 'end';
    };
    document.addEventListener('mousedown', onPointer);
    document.addEventListener('keydown', onKey);
    window.addEventListener('resize', closeAll);
    form.addEventListener('focusout', onFocusOut);
    form.addEventListener('toggle', onToggle, true);
    return () => {
      document.removeEventListener('mousedown', onPointer);
      document.removeEventListener('keydown', onKey);
      window.removeEventListener('resize', closeAll);
      form.removeEventListener('focusout', onFocusOut);
      form.removeEventListener('toggle', onToggle, true);
    };
  }, []);

  function toggle(kind: Kind, code: number, on: boolean) {
    const codes = on ? [...chosen[kind], code] : chosen[kind].filter((c) => c !== code);
    const next: Selection = { ...chosen, [kind]: [...new Set(codes)].sort((a, b) => a - b), page: 1 };
    setChosen(next);
    startTransition(() => router.push(hrefFor(next), { scroll: false }));
  }

  function option(kind: Kind, item: Code, count: Map<number, number>) {
    const n = count.get(item.code) ?? 0;
    const checked = chosen[kind].includes(item.code);
    const id = `${kind}-${item.code}`;
    return (
      <div key={item.code} className={`option${n === 0 && !checked ? ' option-empty' : ''}`}>
        <input
          type="checkbox"
          id={id}
          name={kind}
          value={item.code}
          checked={checked}
          onChange={(e) => toggle(kind, item.code, e.target.checked)}
        />
        <label htmlFor={id}>{item.name}</label>
        <span className="count">
          {n}
          <span className="sr-only"> 件</span>
        </span>
      </div>
    );
  }

  const nameOf = (kind: Kind): string[] => {
    const all: Code[] =
      kind === 'occupation' ? master.occupations.flatMap((g) => g.items) : kind === 'employment' ? master.employments : kind === 'area' ? master.areas : master.stations;
    return chosen[kind].flatMap((code) => all.find((c) => c.code === code)?.name ?? []);
  };

  const simple: { kind: Kind; title: string; items: Code[] }[] = [
    { kind: 'employment', title: '雇用形態', items: master.employments },
    { kind: 'area', title: 'エリア', items: master.areas },
    { kind: 'station', title: '最寄りの乗り場', items: master.stations },
  ];

  return (
    <form
      ref={formRef}
      className="filter-bar"
      method="get"
      action="/"
      aria-label="求人のしぼり込み"
      aria-busy={pending}
      onSubmit={(e) => {
        e.preventDefault();
        startTransition(() => router.push(hrefFor({ ...chosen, page: 1 }), { scroll: false }));
      }}
    >
      {simple.map(({ kind, title, items }) => {
        const count = counts(facets, kind);
        return (
          <Facet key={kind} label={title} names={nameOf(kind)}>
            <fieldset>
              <legend className="sr-only">{title}</legend>
              {items.map((item) => option(kind, item, count))}
            </fieldset>
          </Facet>
        );
      })}

      <Facet label="職種" names={nameOf('occupation')} wide>
        <fieldset>
          <legend className="sr-only">職種</legend>
          {master.occupations.map((group) => (
            <OccupationGroup
              key={group.category}
              group={group}
              picked={group.items.filter((i) => chosen.occupation.includes(i.code)).length}
              renderOption={(item) => option('occupation', item, counts(facets, 'occupation'))}
            />
          ))}
        </fieldset>
      </Facet>

      <button type="submit" className="filter-submit" hidden={enhanced}>
        この条件でさがす
      </button>
      <p className="filter-status" role="status">
        {pending ? '更新しています…' : ''}
      </p>
    </form>
  );
}

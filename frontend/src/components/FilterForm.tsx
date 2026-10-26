'use client';

import { useRouter } from 'next/navigation';
import { useState, useTransition, type ReactNode } from 'react';
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
  // 画面の選択は、チェックを入れた瞬間に変える（サーバーの再描画を待たない）。
  // URL が別の経路（チップの ✕、クリア、戻る）で変わったときは、サーバーの選択に合わせ直す。
  const [chosen, setChosen] = useState(selection);
  const [seen, setSeen] = useState(keyOf(selection));
  if (keyOf(selection) !== seen) {
    setSeen(keyOf(selection));
    setChosen(selection);
  }

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

  const simple: { kind: Kind; title: string; items: Code[] }[] = [
    { kind: 'employment', title: '雇用形態', items: master.employments },
    { kind: 'area', title: 'エリア', items: master.areas },
    { kind: 'station', title: '最寄りの乗り場', items: master.stations },
  ];

  return (
    <form
      className="filter"
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
          <fieldset key={kind}>
            <legend>{title}</legend>
            {items.map((item) => option(kind, item, count))}
          </fieldset>
        );
      })}

      <fieldset>
        <legend>職種</legend>
        {master.occupations.map((group) => (
          <OccupationGroup
            key={group.category}
            group={group}
            picked={group.items.filter((i) => chosen.occupation.includes(i.code)).length}
            renderOption={(item) => option('occupation', item, counts(facets, 'occupation'))}
          />
        ))}
      </fieldset>

      <button type="submit" className="primary-button">
        この条件でさがす
      </button>
      <p className="filter-status" role="status">
        {pending ? '更新しています…' : ''}
      </p>
    </form>
  );
}

import Link from 'next/link';
import type { Chip } from '../lib/search';

/** 選んだ条件のチップ。1 つずつ外せる（リンクなので、JavaScript が無くても動く）。 */
export function SelectedChips({ chips }: { chips: Chip[] }) {
  if (chips.length === 0) return null;
  return (
    <div className="chips" aria-label="選んだ条件">
      <ul>
        {chips.map((chip) => (
          <li key={`${chip.kind}-${chip.code}`}>
            <Link href={chip.removeHref} className="chip" aria-label={`${chip.label}の条件を外す`} scroll={false}>
              {chip.label}
              <span aria-hidden="true"> ✕</span>
            </Link>
          </li>
        ))}
      </ul>
      <Link href="/" className="text-link" scroll={false}>
        条件をすべてクリア
      </Link>
    </div>
  );
}

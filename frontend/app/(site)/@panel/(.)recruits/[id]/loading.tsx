import { RecruitPanel } from '../../../../../src/components/RecruitPanel';

// 詳細が届くまでの骨格。パネルは、押した瞬間に開き（ヘッダーのボタンも使える）、中身だけが、あとから入れ替わる。
// 骨格の動き（光の流れ）は、globals.css が prefers-reduced-motion: reduce で止める
export default function Loading() {
  return (
    <RecruitPanel loading>
      <div className="panel-skeleton" aria-hidden="true">
        <span className="skeleton skeleton-line skeleton-short" />
        <span className="skeleton skeleton-line skeleton-title" />
        <span className="skeleton skeleton-hero" />
        <span className="skeleton skeleton-line" />
        <span className="skeleton skeleton-line" />
        <span className="skeleton skeleton-line skeleton-short" />
      </div>
      <p className="sr-only" role="status">
        求人を読み込んでいます
      </p>
    </RecruitPanel>
  );
}

import { RecruitPanel } from '../../../../../src/components/RecruitPanel';

// 存在しない求人（ID が正しくない・公開が終わった）。パネルの中で知らせる（全ページの 404 に切り替えない）
export default function PanelNotFound() {
  return (
    <RecruitPanel>
      <div className="notice" role="alert">
        <p>この求人は見つかりませんでした。公開が終わったか、URL が正しくない可能性があります。</p>
      </div>
    </RecruitPanel>
  );
}

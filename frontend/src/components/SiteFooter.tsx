/** 全画面のフッター。サイドパネルのある画面では、本文の列（.app-main）の下に置く（サイドパネルの下に潜らせない）。 */
export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="inner">
        <p>表示している求人・法人名は、すべて練習用の架空のデータです。</p>
      </div>
    </footer>
  );
}

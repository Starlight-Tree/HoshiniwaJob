// 診断（/diagnosis）のとき、パネルは空。診断の結果のカードからパネルを開き、同じ診断の URL へ戻すときも、上の @panel/page.tsx と同じ理由で、このページが要る。
// カードを出す (site) の画面を足したら、同じ場所に空のページを足す（足さないと、その画面からパネルを閉じても、URL が戻らない）
export default function PanelEmpty() {
  return null;
}

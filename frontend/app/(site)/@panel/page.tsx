// 一覧（/）のとき、パネルは空。詳細（/recruits/ID）から一覧へ戻る移動で、スロットが「一覧のページ」に当たるようにする。
// 当たるページが無い（default.tsx だけ）と、スロットは前の状態（詳細）のまま残り、本文も同じ一覧のままなので、ルーターが「何も変わらない」と見て、URL も変わらない（実測）
export default function PanelEmpty() {
  return null;
}

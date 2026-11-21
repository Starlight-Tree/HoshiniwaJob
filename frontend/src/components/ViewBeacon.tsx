'use client';

import { useEffect, useRef } from 'react';
import { recordViewAction } from '../actions/recruit-events';

/**
 * 求人の閲覧の記録を、マウントのあとに 1 回だけ送る（何も描かない）。RecruitViewRecorder が、ログイン中の求職者のときだけ置く。
 * 描画のときではなく、クライアントの副作用（useEffect）で呼ぶ: プリフェッチ・ボット・サーバーの描画だけでは、記録されない。
 * 同じ求人では、再描画・開発の StrictMode の二重の実行でも 2 回呼ばない（呼んだ求人を ref に覚える。ref は StrictMode の再実行でも残る）。
 * パネルの中で別の求人へ移ったとき（同じ部品の求人 id だけが変わるとき）は、新しい求人として、もう一度 1 回送る。
 * 失敗しても、何もしない（記録は付随。画面は変えない・出さない）。
 */
export function ViewBeacon({ recruitId }: { recruitId: number }) {
  const sent = useRef<number | null>(null);
  useEffect(() => {
    if (sent.current === recruitId) return;
    sent.current = recruitId;
    void (async () => {
      try {
        await recordViewAction(recruitId);
      } catch {
        // 付随の処理。失敗しても何も変えない
      }
    })();
  }, [recruitId]);
  return null;
}

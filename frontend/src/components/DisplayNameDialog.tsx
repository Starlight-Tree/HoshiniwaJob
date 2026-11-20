'use client';

import { useActionState, useEffect, useRef } from 'react';
import { updateNameAction } from '../actions/auth';
import { initialFormState } from '../lib/form-state';
import { Field } from './Field';

type Props = { displayName: string | null; onClose: () => void };

/**
 * 表示名（ニックネーム）の変更。DocuNavi の「表示名を変更」と同じ 1 欄。標準の <dialog>（showModal）で、
 * Esc で閉じ、フォーカスは中に閉じ込める。外側（背景）の押下では閉じない（標準の <dialog> も閉じない。入力の途中を失わないように）。キャンセルは、親が外す（閉じる）。保存できたら閉じる。
 */
export function DisplayNameDialog({ displayName, onClose }: Props) {
  const [state, formAction, pending] = useActionState(updateNameAction, initialFormState);
  const ref = useRef<HTMLDialogElement>(null);
  const closed = useRef(false);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (typeof dialog.showModal === 'function') dialog.showModal();
    else dialog.setAttribute('open', '');
    dialog.querySelector<HTMLInputElement>('input')?.focus();
  }, []);

  useEffect(() => {
    if (state.saved && !closed.current) {
      closed.current = true;
      onClose();
    }
  }, [state.saved, onClose]);

  return (
    <dialog
      ref={ref}
      className="name-dialog"
      aria-labelledby="name-dialog-title"
      onClose={onClose}
    >
      <form action={formAction} noValidate>
        <h2 id="name-dialog-title">表示名を変更</h2>
        {state.error ? (
          <p className="form-alert" role="alert">
            {state.error}
          </p>
        ) : null}
        <Field name="display_name" label="表示名" autoComplete="nickname" defaultValue={state.values?.display_name ?? displayName ?? ''} error={state.fieldErrors?.display_name} />
        <div className="name-dialog-actions">
          <button type="button" className="outline-button" onClick={onClose}>
            キャンセル
          </button>
          <button type="submit" className="primary-button" disabled={pending}>
            {pending ? '保存中…' : '保存'}
          </button>
        </div>
      </form>
    </dialog>
  );
}

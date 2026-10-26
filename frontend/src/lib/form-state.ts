import type { Field, FieldErrors } from './validation';

// フォームの状態。パスワードは、エラーのあとも返さない（入力し直してもらう）
export type FormState = {
  error?: string;
  fieldErrors?: FieldErrors;
  values?: Partial<Record<Exclude<Field, 'password'>, string>>;
};

export type FormAction = (prev: FormState, formData: FormData) => Promise<FormState>;

export const initialFormState: FormState = {};

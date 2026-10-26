import type { Metadata } from 'next';
import { redirect } from 'next/navigation';
import { gardenLoginAction } from '../../../src/actions/garden';
import { LoginForm } from '../../../src/components/AuthForm';
import { currentGarden } from '../../../src/lib/session';

export const dynamic = 'force-dynamic';
export const metadata: Metadata = { title: '園のログイン' };

export default async function GardenLoginPage() {
  if (await currentGarden()) redirect('/garden');
  return (
    <main className="auth-main">
      <div className="auth-box">
        <h1>園のログイン</h1>
        <LoginForm action={gardenLoginAction} />
      </div>
    </main>
  );
}

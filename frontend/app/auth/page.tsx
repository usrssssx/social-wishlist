import { Suspense } from 'react';

import AuthPage from './auth-page';

export default function AuthRoutePage() {
  return (
    <Suspense fallback={null}>
      <AuthPage />
    </Suspense>
  );
}

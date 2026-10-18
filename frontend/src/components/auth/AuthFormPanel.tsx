import Eye from 'lucide-react/dist/esm/icons/eye';
import EyeOff from 'lucide-react/dist/esm/icons/eye-off';
import { memo, useState, type FormEvent } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import type { AuthMode } from '@/hooks/auth/useAuthPageForm';

export interface AuthFormPanelProps {
  confirmPassword?: string;
  continueWithGoogle: () => void | Promise<void>;
  displayName?: string;
  email: string;
  error?: string | null;
  isForgot?: boolean;
  isGoogleSubmitting?: boolean;
  isSignup?: boolean;
  isSubmitting?: boolean;
  mode: AuthMode;
  notice?: string | null;
  password?: string;
  setConfirmPassword?: (val: string) => void;
  setDisplayName?: (val: string) => void;
  setEmail: (val: string) => void;
  setPassword: (val: string) => void;
  submit: (event: FormEvent<HTMLFormElement>) => void | Promise<void>;
  switchMode: (mode: AuthMode) => void;
}

const GoogleIcon = memo(function GoogleIcon() {
  return (
    <svg aria-hidden="true" className="h-5 w-5" viewBox="0 0 24 24">
      <path
        fill="#4285F4"
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
      />
      <path
        fill="#34A853"
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
      />
      <path
        fill="#FBBC05"
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
      />
      <path
        fill="#EA4335"
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84C6.71 7.31 9.14 5.38 12 5.38z"
      />
    </svg>
  );
});

export function AuthFormPanel({
  confirmPassword = '',
  continueWithGoogle,
  displayName = '',
  email,
  error,
  isGoogleSubmitting = false,
  isForgot = false,
  isSignup = false,
  isSubmitting = false,
  mode,
  notice,
  password = '',
  setConfirmPassword,
  setDisplayName,
  setEmail,
  setPassword,
  submit,
  switchMode,
}: AuthFormPanelProps) {
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  return (
    <section className="flex items-start justify-center bg-white/88 p-5 pb-10 backdrop-blur-xl sm:items-center sm:p-10">
      <div className="w-full max-w-sm">
        <div className="mb-8">
          <p className="inline-flex rounded-full border border-violet-100 bg-violet-50 px-3 py-1.5 text-xs font-black uppercase tracking-[0.18em] text-violet-600">
            {isForgot ? 'Account recovery' : isSignup ? 'Create workspace' : 'Welcome back'}
          </p>
          <h2 className="mt-4 text-3xl font-black tracking-[-0.04em] text-slate-950">
            {isForgot ? 'Reset your password' : isSignup ? 'Create your account' : 'Sign in to your board'}
          </h2>
          <p className="mt-3 text-sm leading-6 text-slate-500">
            {isForgot
              ? 'Enter your email and we will send you a secure recovery link.'
              : isSignup
                ? 'Your account receives its own private ticket workspace.'
                : 'Use the email and password connected to your workspace.'}
          </p>
        </div>

        {!isForgot && (
          <div className="mb-6 space-y-4">
            <div className="grid grid-cols-2 rounded-xl border border-violet-100 bg-violet-50/70 p-1 shadow-inner">
              {(['login', 'signup'] as const).map((item) => (
                <button
                  key={item}
                  type="button"
                  onClick={() => switchMode(item)}
                  className={`rounded-md px-3 py-2 text-sm font-medium transition ${
                    mode === item
                      ? 'bg-white text-violet-700 shadow-sm shadow-violet-100'
                      : 'text-slate-500 hover:text-slate-800'
                  }`}
                >
                  {item === 'login' ? 'Sign in' : 'Sign up'}
                </button>
              ))}
            </div>

            <Button
              type="button"
              variant="outline"
              onClick={continueWithGoogle}
              disabled={isSubmitting || isGoogleSubmitting}
              className="h-11 w-full rounded-xl border-violet-100 bg-white/95 font-bold text-slate-700 shadow-sm shadow-violet-100/60 hover:bg-violet-50 hover:text-violet-700"
            >
              <span className="mr-2 grid h-5 w-5 place-items-center">
                <GoogleIcon />
              </span>
              {isGoogleSubmitting
                ? 'Opening Google…'
                : isSignup
                  ? 'Sign up with Google'
                  : 'Sign in with Google'}
            </Button>

            <div className="flex items-center gap-3 text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
              <span className="h-px flex-1 bg-violet-100" />
              or
              <span className="h-px flex-1 bg-violet-100" />
            </div>
          </div>
        )}

        <form className="space-y-4" onSubmit={submit}>
          {isSignup && (
            <div className="space-y-2">
              <Label htmlFor="display-name">Display name</Label>
              <Input
                id="display-name"
                autoComplete="name"
                value={displayName}
                onChange={(event) => setDisplayName?.(event.target.value)}
                placeholder="Aisha Khan"
                className="h-11 rounded-xl border-violet-200 bg-white/95 px-4 shadow-sm shadow-violet-100/60 placeholder:text-slate-400 focus-visible:ring-2 focus-visible:ring-violet-300"
                required
                maxLength={100}
              />
            </div>
          )}

          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              inputMode="email"
              autoComplete="email"
              autoCapitalize="none"
              spellCheck={false}
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@example.com"
              className="h-11 rounded-xl border-violet-200 bg-white/95 px-4 shadow-sm shadow-violet-100/60 placeholder:text-slate-400 focus-visible:ring-2 focus-visible:ring-violet-300"
              required
            />
          </div>

          {!isForgot && (
            <div className="space-y-2">
              <div className="flex items-center justify-between gap-3">
                <Label htmlFor="password">Password</Label>
                {!isSignup && (
                  <button
                    type="button"
                    onClick={() => switchMode('forgot')}
                    className="text-xs font-semibold text-violet-600 hover:text-violet-800"
                  >
                    Forgot password?
                  </button>
                )}
              </div>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete={isSignup ? 'new-password' : 'current-password'}
                  autoCapitalize="none"
                  spellCheck={false}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  className="h-11 rounded-xl border-violet-200 bg-white/95 px-4 pr-11 shadow-sm shadow-violet-100/60 placeholder:text-slate-400 focus-visible:ring-2 focus-visible:ring-violet-300"
                  minLength={6}
                  required
                />
                <button
                  type="button"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  onClick={() => setShowPassword((visible) => !visible)}
                  className="absolute inset-y-0 right-0 grid w-10 place-items-center text-slate-400 hover:text-violet-600"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>
          )}

          {isSignup && (
            <div className="space-y-2">
              <Label htmlFor="confirm-password">Confirm password</Label>
              <div className="relative">
                <Input
                  id="confirm-password"
                  type={showConfirmPassword ? 'text' : 'password'}
                  autoComplete="new-password"
                  autoCapitalize="none"
                  spellCheck={false}
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword?.(event.target.value)}
                  className="h-11 rounded-xl border-violet-200 bg-white/95 px-4 pr-11 shadow-sm shadow-violet-100/60 placeholder:text-slate-400 focus-visible:ring-2 focus-visible:ring-violet-300"
                  minLength={6}
                  required
                />
                <button
                  type="button"
                  aria-label={showConfirmPassword ? 'Hide confirm password' : 'Show confirm password'}
                  onClick={() => setShowConfirmPassword((visible) => !visible)}
                  className="absolute inset-y-0 right-0 grid w-10 place-items-center text-slate-400 hover:text-violet-600"
                >
                  {showConfirmPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>
          )}

          {error && (
            <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </p>
          )}
          {notice && (
            <p role="status" aria-live="polite" className="rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
              {notice}
            </p>
          )}

          <Button className="h-11 w-full rounded-xl bg-violet-600 font-bold shadow-lg shadow-violet-200/70 hover:bg-violet-700" type="submit" disabled={isSubmitting}>
            {isSubmitting
              ? 'Please wait…'
              : isForgot
                ? 'Send reset link'
                : isSignup
                  ? 'Create account'
                  : 'Sign in'}
          </Button>

          {isForgot && (
            <button
              type="button"
              onClick={() => switchMode('login')}
              className="w-full text-sm font-semibold text-violet-600 hover:text-violet-800"
            >
              Back to sign in
            </button>
          )}
        </form>
      </div>
    </section>
  );
}

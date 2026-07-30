import Eye from 'lucide-react/dist/esm/icons/eye';
import EyeOff from 'lucide-react/dist/esm/icons/eye-off';
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import type { useAuthPageForm } from '@/hooks/auth/useAuthPageForm';

type AuthFormPanelProps = ReturnType<typeof useAuthPageForm>;

export function AuthFormPanel({
  confirmPassword,
  continueWithGoogle,
  displayName,
  email,
  error,
  isGoogleSubmitting,
  isForgot,
  isSignup,
  isSubmitting,
  mode,
  notice,
  password,
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
              <span className="mr-2 grid h-5 w-5 place-items-center rounded-full border border-slate-200 bg-white text-sm font-black text-slate-900">
                G
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
                onChange={(event) => setDisplayName(event.target.value)}
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
              autoComplete="email"
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
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
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
            <p className="rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
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

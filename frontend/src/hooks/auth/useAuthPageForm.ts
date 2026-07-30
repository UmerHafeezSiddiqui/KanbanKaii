import { useState, type FormEvent } from 'react';
import { safeAuthRedirect } from '@/auth/redirect';
import { getSupabaseClient } from '@/lib/supabase';

export type AuthMode = 'login' | 'signup' | 'forgot';

export function useAuthPageForm() {
  const successRedirect = safeAuthRedirect();
  const [mode, setMode] = useState<AuthMode>(() =>
    new URLSearchParams(window.location.search).get('mode') === 'signup' ? 'signup' : 'login',
  );
  const [displayName, setDisplayName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isGoogleSubmitting, setIsGoogleSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const switchMode = (nextMode: AuthMode) => {
    setMode(nextMode);
    setError(null);
    setNotice(null);
    setPassword('');
    setConfirmPassword('');
  };

  const continueWithGoogle = async () => {
    setError(null);
    setNotice(null);
    setIsGoogleSubmitting(true);

    try {
      const supabase = getSupabaseClient();
      const { error: oauthError } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
          redirectTo: `${window.location.origin}${successRedirect}`,
        },
      });
      if (oauthError) throw oauthError;
    } catch (authError) {
      setIsGoogleSubmitting(false);
      setError(
        authError instanceof Error
          ? authError.message
          : 'Google authentication failed. Please try again.',
      );
    }
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setNotice(null);

    if (mode === 'signup' && password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    setIsSubmitting(true);
    try {
      const supabase = getSupabaseClient();

      if (mode === 'forgot') {
        const { error: resetError } = await supabase.auth.resetPasswordForEmail(
          email.trim(),
          { redirectTo: `${window.location.origin}/reset-password` },
        );
        if (resetError) throw resetError;
        setNotice('If an account exists for this email, a password reset link has been sent.');
        return;
      }

      if (mode === 'signup') {
        const { data, error: signUpError } = await supabase.auth.signUp({
          email: email.trim(),
          password,
          options: {
            data: { display_name: displayName.trim() },
          },
        });
        if (signUpError) throw signUpError;

        if (data.session) {
          window.location.assign(successRedirect);
          return;
        }

        setNotice('Account created. Check your email to confirm your account.');
        return;
      }

      const { error: signInError } = await supabase.auth.signInWithPassword({
        email: email.trim(),
        password,
      });
      if (signInError) throw signInError;
      window.location.assign(successRedirect);
    } catch (authError) {
      setError(
        authError instanceof Error
          ? authError.message
          : 'Authentication failed. Please try again.',
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return {
    confirmPassword,
    displayName,
    email,
    error,
    isGoogleSubmitting,
    isForgot: mode === 'forgot',
    isSignup: mode === 'signup',
    isSubmitting,
    mode,
    notice,
    password,
    setConfirmPassword,
    setDisplayName,
    setEmail,
    setPassword,
    submit,
    continueWithGoogle,
    switchMode,
  };
}

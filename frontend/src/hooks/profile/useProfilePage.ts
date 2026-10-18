import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { toast } from 'sonner';
import { updateProfile } from '@/api/profile';
import { useAuth } from '@/auth/AuthContext';

function initialsFor(name: string, email?: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length > 0) {
    return parts.slice(0, 2).map((part) => part[0]).join('').toUpperCase();
  }
  return email?.slice(0, 2).toUpperCase() ?? 'ME';
}

export function useProfilePage() {
  const { user } = useAuth();
  const [name, setName] = useState('');
  const [jobTitle, setJobTitle] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  const initialDisplayName = (user?.user_metadata?.display_name as string | undefined) ?? '';
  const initialJobTitle = (user?.user_metadata?.job_title as string | undefined) ?? '';

  useEffect(() => {
    setName(initialDisplayName);
    setJobTitle(initialJobTitle);
  }, [user?.id, initialDisplayName, initialJobTitle]);

  const initials = useMemo(
    () => initialsFor(name, user?.email),
    [name, user?.email],
  );

  const save = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!user || !name.trim() || isSaving) return;

    setIsSaving(true);
    try {
      await updateProfile(user, {
        displayName: name.trim(),
        jobTitle: jobTitle.trim(),
      });
      toast.success('Profile saved');
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : 'Could not save profile',
      );
    } finally {
      setIsSaving(false);
    }
  };

  return {
    initials,
    isSaving,
    jobTitle,
    name,
    save,
    setJobTitle,
    setName,
    user,
  };
}

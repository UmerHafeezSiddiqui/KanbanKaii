import { useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import {
  notificationSettingsFromUser,
  updateNotificationSettings,
  type NotificationSettings,
} from '@/api/settings';
import { useAuth } from '@/auth/AuthContext';

export function useSettingsPage() {
  const { user } = useAuth();
  const [settings, setSettings] = useState<NotificationSettings>(() =>
    notificationSettingsFromUser(user),
  );
  const [isSaving, setIsSaving] = useState(false);
  const isDirtyRef = useRef(false);

  useEffect(() => {
    if (!isDirtyRef.current) {
      setSettings(notificationSettingsFromUser(user));
    }
  }, [user]);

  const changeSetting = (
    key: keyof NotificationSettings,
    checked: boolean,
  ) => {
    isDirtyRef.current = true;
    setSettings((current) => ({ ...current, [key]: checked }));
  };

  const saveSettings = async () => {
    if (!user || isSaving) return;
    setIsSaving(true);
    try {
      await updateNotificationSettings(user, settings);
      isDirtyRef.current = false;
      toast.success('Settings saved');
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : 'Could not save settings',
      );
    } finally {
      setIsSaving(false);
    }
  };

  return {
    changeSetting,
    isSaving,
    saveSettings,
    settings,
  };
}

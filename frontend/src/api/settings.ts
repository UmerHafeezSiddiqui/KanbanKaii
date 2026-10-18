import type { User } from '@supabase/supabase-js';
import { getSupabaseClient } from '@/lib/supabase';

export interface NotificationSettings {
  newTickets: boolean;
  statusChanges: boolean;
  weeklySummary: boolean;
}

const DEFAULT_NOTIFICATION_SETTINGS: NotificationSettings = {
  newTickets: true,
  statusChanges: true,
  weeklySummary: false,
};

export function notificationSettingsFromUser(
  user: User | null,
): NotificationSettings {
  const stored = user?.user_metadata?.app_preferences?.notifications as
    | Partial<NotificationSettings>
    | undefined;

  return {
    newTickets:
      typeof stored?.newTickets === 'boolean'
        ? stored.newTickets
        : DEFAULT_NOTIFICATION_SETTINGS.newTickets,
    statusChanges:
      typeof stored?.statusChanges === 'boolean'
        ? stored.statusChanges
        : DEFAULT_NOTIFICATION_SETTINGS.statusChanges,
    weeklySummary:
      typeof stored?.weeklySummary === 'boolean'
        ? stored.weeklySummary
        : DEFAULT_NOTIFICATION_SETTINGS.weeklySummary,
  };
}

export async function updateNotificationSettings(
  user: User,
  settings: NotificationSettings,
): Promise<User> {
  const existingPreferences = user.user_metadata.app_preferences ?? {};
  const { data, error } = await getSupabaseClient().auth.updateUser({
    data: {
      ...user.user_metadata,
      app_preferences: {
        ...existingPreferences,
        notifications: settings,
      },
    },
  });

  if (error) throw error;
  return data.user;
}

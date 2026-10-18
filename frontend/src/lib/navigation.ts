export const appNavigateEvent = 'kanbankaii:navigate';

export interface NavigateOptions {
  replace?: boolean;
}

export function navigateTo(path: string, options: NavigateOptions = {}) {
  const currentPath = `${window.location.pathname}${window.location.search}`;
  if (currentPath === path) return;

  if (options.replace) {
    window.history.replaceState({}, '', path);
  } else {
    window.history.pushState({}, '', path);
  }

  window.dispatchEvent(new CustomEvent(appNavigateEvent, { detail: { path } }));
}

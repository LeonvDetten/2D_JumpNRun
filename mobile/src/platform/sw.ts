// Offline support: the service worker precaches the whole app. Optional - without it the app still runs
// (e.g. inside a native shell or on plain http during development).

export function registerServiceWorker(): void {
  if (!("serviceWorker" in navigator) || import.meta.env.DEV) return;
  void import("virtual:pwa-register").then(({ registerSW }) => registerSW({ immediate: true })).catch(() => undefined);
}

// Offline support: the service worker precaches the whole app. Optional - without it the app still runs
// (e.g. inside a native shell or on plain http during development).
// A new version is downloaded in the background; `onUpdate` gets a function that activates it (reload).

export function registerServiceWorker(onUpdate: (apply: () => void) => void): void {
  if (!("serviceWorker" in navigator) || import.meta.env.DEV) return;
  void import("virtual:pwa-register")
    .then(({ registerSW }) => {
      const update = registerSW({
        immediate: true,
        onNeedRefresh: () => onUpdate(() => void update(true)),
        onRegisteredSW: (_url, reg) => {
          // look for a new version every 30 minutes while the app stays open
          if (reg) setInterval(() => void reg.update().catch(() => undefined), 30 * 60 * 1000);
        },
      });
    })
    .catch(() => undefined);
}

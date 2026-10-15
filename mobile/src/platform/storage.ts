// Persistent key-value storage: IndexedDB (kept for home-screen apps, asks for persistence), with
// localStorage as fallback. Kept behind this small interface so a native shell (Capacitor) can swap it.

const DB = "space-pirate";
const STORE = "kv";

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(STORE);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

let dbPromise: Promise<IDBDatabase> | null = null;
function db(): Promise<IDBDatabase> {
  dbPromise ??= openDb();
  return dbPromise;
}

export async function loadText(key: string): Promise<string | null> {
  try {
    const d = await db();
    return await new Promise((resolve, reject) => {
      const req = d.transaction(STORE, "readonly").objectStore(STORE).get(key);
      req.onsuccess = () => resolve(typeof req.result === "string" ? req.result : null);
      req.onerror = () => reject(req.error);
    });
  } catch {
    try {
      return localStorage.getItem(`${DB}:${key}`);
    } catch {
      return null;
    }
  }
}

export async function saveText(key: string, value: string): Promise<void> {
  try {
    const d = await db();
    await new Promise<void>((resolve, reject) => {
      const tx = d.transaction(STORE, "readwrite");
      tx.objectStore(STORE).put(value, key);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  } catch {
    try {
      localStorage.setItem(`${DB}:${key}`, value);
    } catch {
      // storage full or blocked: the game goes on without saving
    }
  }
}

/** Ask the browser not to evict our data (home-screen apps usually get it). */
export async function requestPersistence(): Promise<void> {
  try {
    if (navigator.storage?.persist && !(await navigator.storage.persisted())) await navigator.storage.persist();
  } catch {
    // not supported
  }
}

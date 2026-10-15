// Web Worker: runs the editor's proof search off the main thread (see proof.ts).

import { runSearch, type SearchMessage } from "./proof";

self.onmessage = (e: MessageEvent<{ text: string; prefix: number[]; budget: number }>) => {
  const { text, prefix, budget } = e.data;
  runSearch(text, prefix, budget, (m: SearchMessage) => (self as unknown as Worker).postMessage(m));
};

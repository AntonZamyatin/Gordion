// src/debug.ts
let n = 0;
export function dbg(tag: string, payload?: any) {
  n += 1;
  const t = performance.now().toFixed(1);
  // eslint-disable-next-line no-console
  console.log(`[DBG ${n} @${t}ms] ${tag}`, payload ?? "");
}

// 型別化事件（Stage Proto.Emitter 的 TS 版）
export type Handler<T> = (d: T) => void;
export class Emitter<M extends Record<string, unknown>> {
  private m = new Map<keyof M, Set<Handler<any>>>();
  on<K extends keyof M>(k: K, fn: Handler<M[K]>): () => void {
    if (!this.m.has(k)) this.m.set(k, new Set());
    this.m.get(k)!.add(fn);
    return () => { this.m.get(k)?.delete(fn); };
  }
  emit<K extends keyof M>(k: K, d: M[K]): void {
    for (const fn of [...(this.m.get(k) ?? [])]) { try { fn(d); } catch (e) { console.error(e); } }
  }
}

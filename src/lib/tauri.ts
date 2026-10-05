const hasTauri = () =>
  typeof window !== "undefined" &&
  Boolean((window as unknown as { __TAURI_INTERNALS__?: unknown }).__TAURI_INTERNALS__);

// Safe wrapper for Tauri invoke. Argument keys are camelCase: Tauri maps
// them onto the snake_case Rust parameters.
export async function tauriInvoke<T>(cmd: string, args: Record<string, unknown> = {}): Promise<T> {
  if (hasTauri()) {
    const { invoke } = await import("@tauri-apps/api/core");
    return invoke<T>(cmd, args);
  }
  // Browser preview fallback
  console.log(`[Browser Preview] invoke: ${cmd}`, args);
  return [] as unknown as T;
}

// Subscribes to backend events; returns a disposer that is safe to call
// before the async subscription has settled.
export function listenAll(handlers: Record<string, (payload: unknown) => void>): () => void {
  let disposed = false;
  const unlistens: Array<() => void> = [];
  if (hasTauri()) {
    (async () => {
      try {
        const tev = await import("@tauri-apps/api/event");
        for (const [name, cb] of Object.entries(handlers)) {
          const un = await tev.listen(name, (e) => {
            if (!disposed) cb(e.payload);
          });
          if (disposed) un();
          else unlistens.push(un);
        }
      } catch {
        /* events unavailable */
      }
    })();
  }
  return () => {
    disposed = true;
    unlistens.forEach((u) => {
      try { u(); } catch { /* noop */ }
    });
  };
}

export function errorText(err: unknown): string {
  if (typeof err === "string") return err;
  if (err && typeof err === "object" && "message" in err) {
    const m = (err as { message?: unknown }).message;
    if (typeof m === "string") return m;
  }
  return "";
}

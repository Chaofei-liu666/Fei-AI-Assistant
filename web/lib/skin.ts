export type SkinKind = "none" | "image" | "video";

export type SkinConfig = {
  kind: SkinKind;
  src: string;
  /** 0.2 - 0.95: how much of the background shows through. */
  opacity: number;
  blur: number;
};

const KEY = "fei.skin.v1";
const DEFAULT: SkinConfig = { kind: "none", src: "", opacity: 0.72, blur: 18 };

function load(): SkinConfig {
  if (typeof window === "undefined") return DEFAULT;
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return DEFAULT;
    const parsed = JSON.parse(raw) as Partial<SkinConfig>;
    return {
      kind: parsed.kind === "image" || parsed.kind === "video" ? parsed.kind : "none",
      src: typeof parsed.src === "string" ? parsed.src : "",
      opacity: typeof parsed.opacity === "number" ? Math.min(0.95, Math.max(0.2, parsed.opacity)) : DEFAULT.opacity,
      blur: typeof parsed.blur === "number" ? Math.min(40, Math.max(0, parsed.blur)) : DEFAULT.blur,
    };
  } catch {
    return DEFAULT;
  }
}

let state: SkinConfig = load();
const listeners = new Set<() => void>();

function commit(next: SkinConfig) {
  state = next;
  if (typeof window !== "undefined") {
    try {
      window.localStorage.setItem(KEY, JSON.stringify(state));
    } catch {
      /* quota / private mode */
    }
  }
  listeners.forEach((listener) => listener());
}

export const skin = {
  subscribe(listener: () => void) {
    listeners.add(listener);
    return () => { listeners.delete(listener); };
  },
  snapshot(): SkinConfig {
    return state;
  },
  set(next: SkinConfig) {
    commit(next);
  },
  clear() {
    commit(DEFAULT);
  },
};

export const DEMO_SKIN = "/skins/aurora.jpg";

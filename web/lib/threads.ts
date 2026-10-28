export type ThreadEntry = {
  id: string;
  title: string;
  at: number;
};

type ThreadState = {
  items: ThreadEntry[];
  active: string | null;
};

const KEY = "fei.threads.v1";

function load(): ThreadState {
  if (typeof window === "undefined") return { items: [], active: null };
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return { items: [], active: null };
    const parsed = JSON.parse(raw) as ThreadState;
    return { items: Array.isArray(parsed.items) ? parsed.items : [], active: parsed.active ?? null };
  } catch {
    return { items: [], active: null };
  }
}

let state: ThreadState = load();
const listeners = new Set<() => void>();

function commit(next: ThreadState) {
  state = next;
  if (typeof window !== "undefined") {
    try {
      window.localStorage.setItem(KEY, JSON.stringify(state));
    } catch {
      /* storage may be unavailable */
    }
  }
  listeners.forEach((listener) => listener());
}

export const threads = {
  subscribe(listener: () => void) {
    listeners.add(listener);
    return () => { listeners.delete(listener); };
  },
  snapshot(): ThreadState {
    return state;
  },
  setActive(id: string | null) {
    if (state.active === id) return;
    commit({ ...state, active: id });
  },
  touch(id: string, title = "新对话") {
    const existing = state.items.find((item) => item.id === id);
    if (existing) {
      commit({
        ...state,
        active: id,
        items: state.items.map((item) => (item.id === id ? { ...item, at: Date.now() } : item)),
      });
      return;
    }
    commit({
      active: id,
      items: [{ id, title, at: Date.now() }, ...state.items].slice(0, 40),
    });
  },
  rename(id: string, title: string) {
    const clean = title.trim().slice(0, 28);
    if (!clean) return;
    const existing = state.items.find((item) => item.id === id);
    if (!existing || existing.title === clean) return;
    commit({
      ...state,
      items: state.items.map((item) => (item.id === id ? { ...item, title: clean } : item)),
    });
  },
  remove(id: string) {
    commit({
      active: state.active === id ? null : state.active,
      items: state.items.filter((item) => item.id !== id),
    });
  },
};

export function relativeTime(at: number): string {
  const delta = Date.now() - at;
  const minute = 60_000;
  if (delta < minute) return "刚刚";
  if (delta < 60 * minute) return `${Math.floor(delta / minute)} 分钟前`;
  if (delta < 24 * 60 * minute) return `${Math.floor(delta / (60 * minute))} 小时前`;
  return `${Math.floor(delta / (24 * 60 * minute))} 天前`;
}

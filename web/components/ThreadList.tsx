"use client";

import { useSyncExternalStore } from "react";
import { relativeTime, threads } from "@/lib/threads";

export function ThreadList({ onOpen }: { onOpen?: () => void }) {
  const store = useSyncExternalStore(threads.subscribe, threads.snapshot, threads.snapshot);

  if (store.items.length === 0) {
    return <p className="side-empty">还没有会话，发一句话就开始</p>;
  }

  return <div className="thread-list">
    {store.items.map((item) => <button
      key={item.id}
      className={`thread-item ${store.active === item.id ? "active" : ""}`}
      onClick={() => { threads.setActive(item.id); onOpen?.(); }}
    >
      <span className="thread-title">{item.title}</span>
      <span className="thread-time">{relativeTime(item.at)}</span>
    </button>)}
  </div>;
}

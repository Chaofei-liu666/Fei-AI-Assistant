"use client";

import { useEffect, useSyncExternalStore } from "react";
import { DEMO_SKIN, skin } from "@/lib/skin";

export function SkinLayer() {
  const config = useSyncExternalStore(skin.subscribe, skin.snapshot, skin.snapshot);
  const demo = typeof window !== "undefined" && new URLSearchParams(window.location.search).get("skin") === "demo";
  const active = demo ? { ...config, kind: "image" as const, src: DEMO_SKIN } : config;
  const on = active.kind !== "none" && Boolean(active.src);

  useEffect(() => {
    const root = document.documentElement;
    root.dataset.skin = on ? "on" : "off";
    root.style.setProperty("--skin-veil", String((1 - active.opacity).toFixed(2)));
    root.style.setProperty("--skin-blur", `${active.blur}px`);
  }, [on, active.opacity, active.blur]);

  if (!on) return null;

  return <div className="skin-layer" aria-hidden="true">
    {active.kind === "video"
      ? <video src={active.src} autoPlay muted loop playsInline />
      : <img src={active.src} alt="" />}
    <div className="skin-veil" />
  </div>;
}

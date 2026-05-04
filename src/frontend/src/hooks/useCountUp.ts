"use client";

import { useEffect, useState } from "react";

/**
 * Anime ``value`` de 0 jusqu’à la cible (ease-out cubique). ``null`` → affichage chargement / pas encore prêt.
 */
export function useCountUp(value: number | null, durationMs = 880): number {
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    if (value == null) {
      setDisplay(0);
      return;
    }

    const mq =
      typeof window !== "undefined" ? window.matchMedia("(prefers-reduced-motion: reduce)") : null;
    if (mq?.matches) {
      setDisplay(value);
      return;
    }

    const t0 = performance.now();
    let raf = 0;

    const tick = (now: number) => {
      const p = Math.min(1, (now - t0) / durationMs);
      const eased = 1 - (1 - p) ** 3;
      setDisplay(Math.round(value * eased));
      if (p < 1) raf = requestAnimationFrame(tick);
    };

    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, durationMs]);

  return display;
}

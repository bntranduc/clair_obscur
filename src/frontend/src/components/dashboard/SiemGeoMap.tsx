"use client";

import { useEffect, useRef } from "react";
import type { Map, CircleMarker, LatLngBounds } from "leaflet";
import type { SiemGeoLogPoint } from "@/types/siemAnalytics";
import "leaflet/dist/leaflet.css";

function tooltipText(p: SiemGeoLogPoint): string {
  const parts = [p.timestamp, p.source_ip, p.log_source, p.geolocation_country].filter(
    (x): x is string => typeof x === "string" && x.length > 0,
  );
  return parts.length ? parts.join(" · ") : `${p.lat.toFixed(4)}, ${p.lon.toFixed(4)}`;
}

/** Carte OSM (Leaflet). Utilise les exports nommés du module ``leaflet`` (compatible Next / Turbopack). */
export default function SiemGeoMap({ points }: { points: SiemGeoLogPoint[] }) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const hostRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<Map | null>(null);
  const markersRef = useRef<CircleMarker[]>([]);

  useEffect(() => {
    const host = hostRef.current;
    const wrap = wrapRef.current;
    if (!host) return;

    let cancelled = false;
    let resizeObserver: ResizeObserver | null = null;
    let resizeTimer: ReturnType<typeof setTimeout> | undefined;

    void (async () => {
      const L = await import("leaflet");
      if (cancelled || !hostRef.current) return;

      const { map: createMap, tileLayer: createTileLayer, circleMarker: createCircleMarker, latLngBounds } = L;

      markersRef.current.forEach((m) => {
        try {
          m.remove();
        } catch {
          /* ignore */
        }
      });
      markersRef.current = [];
      if (mapRef.current) {
        try {
          mapRef.current.remove();
        } catch {
          /* ignore */
        }
        mapRef.current = null;
      }
      host.replaceChildren();

      const map = createMap(host, {
        zoomControl: true,
        attributionControl: true,
        worldCopyJump: true,
      });
      mapRef.current = map;

      createTileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        maxZoom: 19,
      }).addTo(map);

      if (points.length > 0) {
        let bounds: LatLngBounds | null = null;
        for (const p of points) {
          const ll: [number, number] = [p.lat, p.lon];
          bounds = bounds ? bounds.extend(ll) : latLngBounds(ll, ll);
          const m = createCircleMarker(ll, {
            radius: 5,
            color: "#93c5fd",
            weight: 1,
            fillColor: "#3b82f6",
            fillOpacity: 0.82,
          }).addTo(map);
          m.bindTooltip(tooltipText(p));
          markersRef.current.push(m);
        }
        if (bounds?.isValid()) {
          map.fitBounds(bounds, { padding: [32, 32], maxZoom: 12 });
        }
      } else {
        map.setView([20, 0], 2);
      }

      const fixSize = () => {
        if (cancelled || !mapRef.current) return;
        try {
          mapRef.current.invalidateSize(true);
        } catch {
          /* ignore */
        }
      };
      requestAnimationFrame(fixSize);
      resizeTimer = setTimeout(fixSize, 200);

      if (typeof ResizeObserver !== "undefined" && wrap) {
        resizeObserver = new ResizeObserver(() => fixSize());
        resizeObserver.observe(wrap);
      }
    })();

    return () => {
      cancelled = true;
      if (resizeTimer !== undefined) clearTimeout(resizeTimer);
      resizeObserver?.disconnect();
      markersRef.current.forEach((m) => {
        try {
          m.remove();
        } catch {
          /* ignore */
        }
      });
      markersRef.current = [];
      if (mapRef.current) {
        try {
          mapRef.current.remove();
        } catch {
          /* ignore */
        }
        mapRef.current = null;
      }
      host.replaceChildren();
    };
  }, [points]);

  return (
    <div ref={wrapRef} className="relative z-0 h-[380px] w-full min-w-0">
      <div
        ref={hostRef}
        className="h-full w-full overflow-hidden rounded-lg border border-white/[0.08] bg-zinc-950/40 [&_.leaflet-container]:z-0 [&_.leaflet-container]:h-full [&_.leaflet-container]:w-full [&_.leaflet-container]:font-sans"
      />
    </div>
  );
}

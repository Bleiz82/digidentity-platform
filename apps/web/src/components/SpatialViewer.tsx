"use client";

import { useEffect, useRef } from "react";
import type { SceneId } from "@/hooks/useSpatialSync";

export interface SpatialViewerProps {
  sceneId: SceneId;
  className?: string;
}

const SCENE_IMAGES: Record<SceneId, string> = {
  "villa-entrance": "/360/villa-entrance.jpg",
  "master-suite": "/360/master-suite.jpg",
  "infinity-pool": "/360/infinity-pool.jpg",
};

type PSVInstance = {
  setPanorama(src: string, opts?: { transition?: number }): Promise<unknown>;
  destroy(): void;
};

/**
 * Wraps @photo-sphere-viewer/core in a React component.
 * Dynamic import avoids SSR breakage (PSV needs browser globals).
 * BIBLE §6.6 — Spatial Experience viewer.
 */
export function SpatialViewer({ sceneId, className }: SpatialViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<PSVInstance | null>(null);

  // Mount viewer once
  useEffect(() => {
    if (!containerRef.current) return;
    let destroyed = false;

    import("@photo-sphere-viewer/core")
      .then(({ Viewer }) => {
        if (destroyed || !containerRef.current) return;
        viewerRef.current = new Viewer({
          container: containerRef.current,
          panorama: SCENE_IMAGES[sceneId],
          defaultZoomLvl: 0,
          navbar: false,
          touchmoveTwoFingers: true,
        }) as unknown as PSVInstance;
      })
      .catch(() => undefined);

    return () => {
      destroyed = true;
      viewerRef.current?.destroy();
      viewerRef.current = null;
    };
    // sceneId intentionally omitted — initial scene handled here, changes below
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Transition to new scene when sceneId prop changes
  useEffect(() => {
    if (!viewerRef.current) return;
    viewerRef.current
      .setPanorama(SCENE_IMAGES[sceneId], { transition: 800 })
      .catch(() => undefined);
  }, [sceneId]);

  return (
    <div
      ref={containerRef}
      className={className}
      data-testid="spatial-viewer"
      style={{ width: "100%", height: "100%", minHeight: "300px" }}
    />
  );
}

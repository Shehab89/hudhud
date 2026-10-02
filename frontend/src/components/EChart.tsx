"use client";

import { useEffect, useRef } from "react";
import type { EChartsOption } from "echarts";

/** Resolve "var(--token)" strings inside an option tree against the current theme. */
function resolveVars<T>(value: T, styles: CSSStyleDeclaration): T {
  if (typeof value === "string") {
    return value.replace(/var\((--[\w-]+)\)/g, (_, name) => styles.getPropertyValue(name).trim() || "#888") as T;
  }
  if (Array.isArray(value)) return value.map((v) => resolveVars(v, styles)) as T;
  if (value && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value)) out[k] = resolveVars(v, styles);
    return out as T;
  }
  return value;
}

const BASE: EChartsOption = {
  textStyle: { fontFamily: "inherit", color: "var(--muted)" },
  grid: { left: 8, right: 16, top: 28, bottom: 8, containLabel: true },
  tooltip: { backgroundColor: "var(--surface)", borderColor: "var(--line)", textStyle: { color: "var(--ink)" } },
  legend: { textStyle: { color: "var(--muted)" }, top: 0, type: "scroll" },
};

export default function EChart({ option, height = 280, ariaLabel, mapGeoUrl }: {
  option: EChartsOption; height?: number; ariaLabel: string; mapGeoUrl?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let disposed = false;
    let chart: import("echarts").ECharts | undefined;
    let observer: MutationObserver | undefined;
    let resize: ResizeObserver | undefined;
    (async () => {
      const echarts = await import("echarts");
      if (mapGeoUrl && !echarts.getMap("yemen")) {
        const geo = await fetch(mapGeoUrl).then((r) => r.json());
        echarts.registerMap("yemen", geo);
      }
      if (disposed || !ref.current) return;
      chart = echarts.init(ref.current, undefined, { renderer: "canvas" });
      const rtl = document.documentElement.dir === "rtl";
      const render = () => {
        const styles = getComputedStyle(document.documentElement);
        const merged = { ...BASE, ...option, grid: { ...(BASE.grid as object), ...((option.grid as object) || {}) } };
        if (rtl && merged.legend && !Array.isArray(merged.legend)) (merged.legend as Record<string, unknown>).align = "right";
        chart?.setOption(resolveVars(merged, styles), true);
      };
      render();
      observer = new MutationObserver(render);
      observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
      resize = new ResizeObserver(() => chart?.resize());
      resize.observe(ref.current);
    })();
    return () => {
      disposed = true;
      observer?.disconnect();
      resize?.disconnect();
      chart?.dispose();
    };
  }, [option, mapGeoUrl]);

  return <div ref={ref} role="img" aria-label={ariaLabel} style={{ height, width: "100%" }} />;
}

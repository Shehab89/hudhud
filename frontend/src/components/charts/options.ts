/** Server-side builders for ECharts options. Colours are CSS variables, resolved in the browser per theme. */
import type { EChartsOption } from "echarts";

const AXIS = { axisLine: { lineStyle: { color: "var(--line)" } }, axisLabel: { color: "var(--muted)" }, splitLine: { lineStyle: { color: "var(--line)" } } };

export function stackedArea(days: string[], series: { name: string; data: number[]; color?: string }[], rtl = false): EChartsOption {
  return {
    tooltip: { trigger: "axis" },
    legend: { top: 0 },
    grid: { top: 36 },
    xAxis: { type: "category", data: days, boundaryGap: false, inverse: rtl, ...AXIS, splitLine: { show: false } },
    yAxis: { type: "value", position: rtl ? "right" : "left", minInterval: 1, ...AXIS },
    series: series.map((s) => ({
      name: s.name, type: "line", stack: "total", smooth: 0.25, symbol: "none", data: s.data,
      areaStyle: { opacity: 0.85 }, lineStyle: { width: 0.5 }, itemStyle: s.color ? { color: s.color } : undefined,
    })),
  };
}

export function lineSeries(points: { day: string; articles: number }[], rtl = false): EChartsOption {
  return {
    tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: points.map((p) => p.day.slice(0, 10)), inverse: rtl, ...AXIS, splitLine: { show: false } },
    yAxis: { type: "value", position: rtl ? "right" : "left", minInterval: 1, ...AXIS },
    series: [{ type: "bar", data: points.map((p) => p.articles), itemStyle: { color: "var(--accent-2)", borderRadius: [2, 2, 0, 0] } }],
  };
}

export function groupedBars(categories: string[], series: { name: string; data: number[]; color?: string }[], opts: { percent?: boolean; rtl?: boolean } = {}): EChartsOption {
  return {
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    legend: { top: 0 },
    grid: { top: 36 },
    xAxis: { type: "value", inverse: opts.rtl, axisLabel: { color: "var(--muted)", formatter: opts.percent ? "{value}%" : "{value}" }, max: opts.percent ? 100 : undefined, splitLine: { lineStyle: { color: "var(--line)" } } },
    yAxis: { type: "category", data: categories, inverse: true, position: opts.rtl ? "right" : "left", axisLabel: { color: "var(--ink)", width: 160, overflow: "truncate" }, axisLine: { lineStyle: { color: "var(--line)" } } },
    series: series.map((s) => ({ name: s.name, type: "bar", data: opts.percent ? s.data.map((v) => Math.round(v * 1000) / 10) : s.data, barMaxWidth: 10, itemStyle: s.color ? { color: s.color } : undefined })),
  };
}

export function donut(items: { name: string; value: number; color?: string }[]): EChartsOption {
  return {
    tooltip: { trigger: "item" },
    legend: { bottom: 0, top: "auto" },
    series: [{
      type: "pie", radius: ["48%", "72%"], center: ["50%", "44%"], label: { show: false },
      data: items.map((i) => ({ name: i.name, value: i.value, itemStyle: i.color ? { color: i.color } : undefined })),
    }],
  };
}

export function choropleth(regions: { code: string; name: string; value: number }[], places: { name: string; lat: number; lon: number; value: number }[], seriesName: string): EChartsOption {
  const max = Math.max(1, ...regions.map((r) => r.value));
  return {
    tooltip: { trigger: "item", formatter: "{b}: {c}" },
    visualMap: { min: 0, max, left: 8, bottom: 8, calculable: false, inRange: { color: ["var(--surface-2)", "var(--accent-2)"] }, textStyle: { color: "var(--muted)" } },
    geo: {
      map: "yemen", roam: true, nameProperty: "code", nameMap: Object.fromEntries(regions.map((r) => [r.code, r.name])),
      itemStyle: { borderColor: "var(--bg)", areaColor: "var(--surface-2)" },
      emphasis: { label: { show: false }, itemStyle: { areaColor: "var(--accent)" } },
    },
    series: [
      { name: seriesName, type: "map", geoIndex: 0, data: regions.map((r) => ({ name: r.name, value: r.value })) },
      {
        name: seriesName, type: "scatter", coordinateSystem: "geo",
        data: places.filter((p) => p.value > 0).map((p) => ({ name: p.name, value: [p.lon, p.lat, p.value], symbolSize: Math.min(22, 5 + Math.sqrt(p.value) * 2) })),
        tooltip: { formatter: "{b}" }, itemStyle: { color: "var(--accent)", opacity: 0.85 },
      },
    ],
  };
}

export function multiLine(days: string[], series: { name: string; data: number[]; color?: string }[], rtl = false): EChartsOption {
  return {
    tooltip: { trigger: "axis" },
    legend: { top: 0 },
    grid: { top: 36 },
    xAxis: { type: "category", data: days, boundaryGap: false, inverse: rtl, ...AXIS, splitLine: { show: false } },
    yAxis: { type: "value", position: rtl ? "right" : "left", minInterval: 1, ...AXIS },
    series: series.map((s) => ({
      name: s.name, type: "line", smooth: 0.25, symbol: "none", data: s.data, lineStyle: { width: 2 },
      itemStyle: s.color ? { color: s.color } : undefined,
    })),
  };
}

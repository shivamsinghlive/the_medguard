import { useEffect, useState } from 'react'

// Chart colors come from the same CSS variables as the page, so ECharts and the
// canvas follow light/dark mode. Groups: cobalt, teal, scan, ink. Tangerine is
// reserved for review evidence.
const GROUP_TOKENS = ['brand-500', 'teal-500', 'brand-300', 'ink-700']

export function token(name: string, alpha = 1): string {
  const raw = getComputedStyle(document.documentElement).getPropertyValue(`--${name}`).trim()
  const rgb = raw ? raw.split(/\s+/).join(',') : '128,128,128'
  return alpha === 1 ? `rgb(${rgb})` : `rgba(${rgb},${alpha})`
}

export const groupColor = (index: number) => token(GROUP_TOKENS[index % GROUP_TOKENS.length])
export const reviewColor = () => token('review-500')

export const prefersReducedMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches

/** Re-render on light/dark changes; returns the active scheme. */
export function useScheme(): 'light' | 'dark' {
  const query = '(prefers-color-scheme: dark)'
  const [scheme, setScheme] = useState<'light' | 'dark'>(() => (matchMedia(query).matches ? 'dark' : 'light'))
  useEffect(() => {
    const media = matchMedia(query)
    const update = () => setScheme(media.matches ? 'dark' : 'light')
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [])
  return scheme
}

const axisDefaults = (horizontalGrid: boolean) => ({
  axisLine: { lineStyle: { color: token('slate-300') } },
  axisTick: { show: false },
  axisLabel: { color: token('ink-500'), fontSize: 11 },
  nameTextStyle: { color: token('ink-500'), fontSize: 11 },
  splitLine: { show: horizontalGrid, lineStyle: { color: token('slate-200') } },
})

function mergeAxes(axis: any, horizontalGrid: (a: any) => boolean) {
  if (!axis) return axis
  const one = (a: any) => {
    const d = axisDefaults(horizontalGrid(a))
    return { ...d, ...a, axisLabel: { ...d.axisLabel, ...a.axisLabel }, splitLine: { ...d.splitLine, ...a.splitLine },
      axisLine: { ...d.axisLine, ...a.axisLine }, nameTextStyle: { ...d.nameTextStyle, ...a.nameTextStyle } }
  }
  return Array.isArray(axis) ? axis.map(one) : one(axis)
}

/** The medguard chart theme: transparent background, horizontal-only grid, palette tooltips. */
export function themed(option: any): any {
  const reduced = prefersReducedMotion()
  return {
    animation: !reduced,
    animationDuration: 500,
    backgroundColor: 'transparent',
    color: GROUP_TOKENS.map((t) => token(t)),
    textStyle: { fontFamily: '"Instrument Sans", system-ui, sans-serif', color: token('ink-700') },
    grid: { left: 8, right: 16, top: 36, bottom: 8, containLabel: true },
    legend: { textStyle: { color: token('ink-700') }, icon: 'roundRect', itemWidth: 10, itemHeight: 10 },
    tooltip: {
      trigger: 'axis', backgroundColor: token('ink-900'), borderColor: token('ink-900'),
      textStyle: { color: token('card'), fontSize: 12 }, extraCssText: 'border-radius:10px;box-shadow:0 10px 24px rgba(0,0,0,.18);',
    },
    ...option,
    ...(option.legend ? { legend: { textStyle: { color: token('ink-700') }, icon: 'roundRect', itemWidth: 10, itemHeight: 10, ...option.legend } } : {}),
    ...(option.tooltip ? { tooltip: { backgroundColor: token('ink-900'), borderColor: token('ink-900'),
      textStyle: { color: token('card'), fontSize: 12 }, extraCssText: 'border-radius:10px;', ...option.tooltip } } : {}),
    xAxis: mergeAxes(option.xAxis, () => false),
    yAxis: mergeAxes(option.yAxis, (a) => a?.type !== 'category'),
  }
}

export function startRum(): () => void {
  const endpoint = import.meta.env.VITE_RUM_ENDPOINT as string | undefined
  if (!endpoint || typeof window === 'undefined' || typeof performance === 'undefined') return () => undefined

  const send = (metric: string, value: number) => {
    if (!Number.isFinite(value) || value < 0) return
    const body = JSON.stringify({ metric, value: Math.round(value * 100) / 100, page: window.location.pathname.slice(0, 120) || '/' })
    if (navigator.sendBeacon) navigator.sendBeacon(endpoint, new Blob([body], { type: 'application/json' }))
    else void fetch(endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body, keepalive: true })
  }

  const startedAt = performance.now()
  const onLoad = () => send('navigation', performance.now() - startedAt)
  window.addEventListener('load', onLoad, { once: true })
  return () => window.removeEventListener('load', onLoad)
}

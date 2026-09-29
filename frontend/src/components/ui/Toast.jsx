import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react'

const ToastContext = createContext(null)

let nextId = 1

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const timers = useRef(new Map())

  const dismiss = useCallback((key) => {
    // Salida en dos fases: primero marca leaving (transición CSS 160ms),
    // luego desmonta. Sin esto el toast desaparecería de golpe.
    setToasts((prev) => prev.map((t) => (t.key === key ? { ...t, leaving: true } : t)))
    const t = timers.current.get(key)
    if (t) clearTimeout(t)
    timers.current.delete(key)
    const rm = setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.key !== key))
      timers.current.delete(`rm:${key}`)
    }, 180)
    timers.current.set(`rm:${key}`, rm)
  }, [])

  const push = useCallback((type, message, duration = 6000) => {
    const key = nextId++
    setToasts((prev) => [...prev.slice(-4), { key, type, message }])
    const t = setTimeout(() => dismiss(key), duration)
    timers.current.set(key, t)
  }, [dismiss])

  const toast = useMemo(() => ({
    ok: (m, d) => push('ok', m, d),
    err: (m, d) => push('err', m, d),
    info: (m, d) => push('info', m, d),
  }), [push])

  const value = useMemo(() => ({ toast }), [toast])

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toasts" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.key} className={`toast toast-${t.type}${t.leaving ? ' toast-out' : ''}`} role="alert">
            <span className="toast-msg">{t.message}</span>
            <button type="button" className="toast-close" onClick={() => dismiss(t.key)} aria-label="Cerrar">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4"><path d="M6 6l12 12M18 6L6 18"/></svg>
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast debe usarse dentro de <ToastProvider>')
  return ctx.toast
}
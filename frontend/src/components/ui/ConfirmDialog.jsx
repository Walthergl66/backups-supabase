import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'

const DialogContext = createContext(null)

const noop = () => {}

export function DialogProvider({ children }) {
  const [state, setState] = useState(null) // { kind, title, message, confirmLabel, danger, initial }
  const resolver = useRef(noop)
  const inputRef = useRef(null)

  useEffect(() => {
    if (state?.kind === 'prompt' && inputRef.current) inputRef.current.focus()
  }, [state])

  const close = useCallback((value) => {
    setState(null)
    const r = resolver.current
    resolver.current = noop
    r(value)
  }, [])

  const open = useCallback((payload) => {
    resolver.current = payload.resolve
    setState({
      title: 'Confirmar',
      confirmLabel: 'Confirmar',
      message: '',
      ...payload,
    })
  }, [])

  const confirm = useCallback((message, options = {}) =>
    new Promise((resolve) => open({ kind: 'confirm', message, resolve, ...options })), [open])

  const prompt = useCallback((message, options = {}) =>
    new Promise((resolve) => open({ kind: 'prompt', message, resolve, ...options })), [open])

  const onKeyDown = useCallback((e) => {
    if (e.key === 'Escape') {
      if (state?.kind === 'prompt') close(null)
      else close(false)
    }
  }, [state, close])

  const value = useMemo(() => ({ confirm, prompt }), [confirm, prompt])

  return (
    <DialogContext.Provider value={value}>
      {children}
      {state && (
        <div
          className="dimmer diag"
          role="dialog"
          aria-modal="true"
          aria-label={state.title}
          onKeyDown={onKeyDown}
        >
          <form
            className="diag-card"
            onSubmit={(e) => {
              e.preventDefault()
              close(state.kind === 'prompt' ? inputRef.current?.value?.trim() ?? '' : true)
            }}
          >
            <h3>{state.title}</h3>
            <p>{state.message}</p>
            {state.kind === 'prompt' && (
              <div className="field">
                <input
                  ref={inputRef}
                  className="input"
                  type="text"
                  defaultValue={state.initial}
                  required
                />
              </div>
            )}
            <div className="diag-actions">
              <button type="button" className="btn btn-ghost" autoFocus={state.kind === 'confirm'} onClick={() => close(state.kind === 'prompt' ? null : false)}>
                Cancelar
              </button>
              <button type="submit" className={`btn ${state.danger ? 'btn-danger' : 'btn-primary'}`}>
                {state.confirmLabel}
              </button>
            </div>
          </form>
        </div>
      )}
    </DialogContext.Provider>
  )
}

export function useDialog() {
  const ctx = useContext(DialogContext)
  if (!ctx) throw new Error('useDialog debe usarse dentro de <DialogProvider>')
  return ctx
}
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext.jsx'
import { ApiError } from '../../services/http.js'
import Flash from '../../components/ui/Flash.jsx'

export default function Login() {
  const { login } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [code, setCode] = useState('')
  const [totpPending, setTotpPending] = useState(false)
  const [error, setError] = useState('')
  const [sending, setSending] = useState(false)
  const navigate = useNavigate()

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setSending(true)
    try {
      await login(username, password, totpPending ? code : undefined)
      navigate('/', { replace: true })
    } catch (err) {
      if (err instanceof ApiError && err.data?.totp_required) {
        setTotpPending(true)
        setCode('')
        setError('Ingresa el código de tu aplicación de autenticación.')
      } else {
        setError(err instanceof ApiError ? err.message : 'Error inesperado')
      }
    } finally {
      setSending(false)
    }
  }

  const resetTotp = () => {
    setTotpPending(false)
    setCode('')
    setError('')
  }

  return (
    <div className="login-page login-glow">
      <div className="login-card">
        <div className="login-logo">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"><path d="M12 3v9l3 3"/><path d="M5 15a7 7 0 1 1 2.1 5"/></svg>
        </div>
        <h1>Supabase Backups</h1>
        <p className="muted" style={{ marginTop: 0, fontSize: 13 }}>Bienvenido de nuevo. Ingresa con tu usuario del panel.</p>

        {error && <Flash type="err">{error}</Flash>}

        <form onSubmit={submit}>
          {!totpPending ? (
            <>
              <div className="field">
                <label className="label">Usuario</label>
                <input
                  className="input"
                  autoFocus
                  autoComplete="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                />
              </div>
              <div className="field">
                <label className="label">Contraseña</label>
                <input
                  className="input"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
            </>
          ) : (
            <>
              <div className="field">
                <label className="label">Código 2FA</label>
                <input
                  className="input"
                  autoFocus
                  inputMode="numeric"
                  pattern="[0-9]*"
                  autoComplete="one-time-code"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                />
              </div>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={resetTotp}
                style={{ marginBottom: 12 }}
              >
                Iniciar con otro usuario
              </button>
            </>
          )}
          <button className="btn btn-primary btn-block" disabled={sending || !username || !password || (totpPending && !code)}>
            {sending ? 'Ingresando…' : totpPending ? 'Verificar' : 'Ingresar'}
          </button>
        </form>
      </div>
    </div>
  )
}

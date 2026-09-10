import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext.jsx'
import { ApiError } from '../../services/http.js'
import Flash from '../../components/ui/Flash.jsx'

export default function Login() {
  const { login } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [sending, setSending] = useState(false)
  const navigate = useNavigate()

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setSending(true)
    try {
      await login(username, password)
      navigate('/', { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Error inesperado')
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="login-page login-glow">
      <div className="login-card">
        <div className="login-logo">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"><path d="M12 3v9l3 3"/><path d="M5 15a7 7 0 1 1 2.1 5"/></svg>
        </div>
        <h1 style={{ margin: '0 0 4px', fontSize: 20 }}>Supabase Backups</h1>
        <p className="muted" style={{ marginTop: 0, fontSize: 13 }}>Bienvenido de nuevo. Ingresa con tu usuario del panel.</p>

        {error && <Flash type="err">{error}</Flash>}

        <form onSubmit={submit}>
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
          <button className="btn btn-primary btn-block" disabled={sending || !username || !password}>
            {sending ? 'Ingresando…' : 'Ingresar'}
          </button>
        </form>
      </div>
    </div>
  )
}
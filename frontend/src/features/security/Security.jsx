import { useState } from 'react'
import { totpSetup, totpConfirm, totpDisable } from '../../services/totp.js'
import { useAuth } from '../auth/AuthContext.jsx'
import { ApiError } from '../../services/http.js'
import PageHead from '../../components/ui/PageHead.jsx'
import Flash from '../../components/ui/Flash.jsx'

export default function Security() {
  const { user } = useAuth()
  const [active, setActive] = useState(Boolean(user?.totp_enabled))
  const [qr, setQr] = useState(null)
  const [secret, setSecret] = useState('')
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [sending, setSending] = useState(false)

  const enabling = !active && qr

  const startSetup = async () => {
    setError('')
    setSending(true)
    try {
      const r = await totpSetup()
      setQr(r.qr_svg)
      setSecret(r.secret)
      setCode('')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Error inesperado')
    } finally {
      setSending(false)
    }
  }

  const confirm = async (e) => {
    e.preventDefault()
    setError('')
    setSending(true)
    try {
      await totpConfirm(code)
      setActive(true)
      setQr(null)
      setSecret('')
      setCode('')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Error inesperado')
    } finally {
      setSending(false)
    }
  }

  const disable = async (e) => {
    e.preventDefault()
    setError('')
    setSending(true)
    try {
      await totpDisable(code)
      setActive(false)
      setCode('')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Error inesperado')
    } finally {
      setSending(false)
    }
  }

  return (
    <>
      <PageHead title="Seguridad" sub="Verificación en dos pasos (TOTP) de tu cuenta del panel." />

      {error && <Flash type="err">{error}</Flash>}

      <div className="card" style={{ maxWidth: 480 }}>
        <div className="card-body">
          <div className="field">
            <span className="label">Aplicación de autenticación</span>
            <p className="hint" style={{ marginTop: 4 }}>
              {active
                ? '2FA activo: al iniciar sesión se pedirá un código de 6 dígitos además de la contraseña.'
                : '2FA desactivado: se recomienda activarlo para proteger tu cuenta.'}
            </p>
          </div>

          {!enabling && !active && (
            <div className="inline-actions">
              <button className="btn btn-primary" onClick={startSetup} disabled={sending}>
                {sending ? 'Generando…' : 'Activar 2FA'}
              </button>
            </div>
          )}

          {enabling && (
            <>
              <p className="hint">
                Escanea el código QR con tu app (Google Authenticator, Authy, 1Password…)
                y escribe el código de 6 dígitos.
              </p>
              {qr && (
                <div style={{ marginBottom: 16 }}>
                  <img src={qr} alt="QR TOTP" style={{ width: 200, height: 200 }} />
                </div>
              )}
              <div className="field">
                <label className="label">Código de verificación</label>
                <input
                  className="input"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  autoComplete="one-time-code"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                />
              </div>
              <div className="inline-actions">
                <button className="btn btn-primary" onClick={confirm} disabled={sending || code.length < 6}>
                  {sending ? 'Verificando…' : 'Confirmar y activar'}
                </button>
                <button type="button" className="btn btn-ghost" onClick={() => { setQr(null); setSecret(''); setCode(''); setError('') }}>
                  Cancelar
                </button>
              </div>
              {secret && (
                <p className="hint">
                  Si no puedes escanear el QR, usa este secreto manualmente:{' '}
                  <code>{secret}</code>
                </p>
              )}
            </>
          )}

          {active && (
            <>
              <p className="hint">
                Para desactivarlo, escribe un código válido de tu app. Si pierdes el acceso,
                contacta con un administrador para restablecer la cuenta.
              </p>
              <form onSubmit={disable}>
                <div className="field">
                  <label className="label">Código de verificación</label>
                  <input
                    className="input"
                    inputMode="numeric"
                    pattern="[0-9]*"
                    autoComplete="one-time-code"
                    value={code}
                    onChange={(e) => setCode(e.target.value)}
                  />
                </div>
                <div className="inline-actions">
                  <button className="btn btn-danger" disabled={sending || code.length < 6}>
                    {sending ? 'Desactivando…' : 'Desactivar 2FA'}
                  </button>
                </div>
              </form>
            </>
          )}
        </div>
      </div>
    </>
  )
}
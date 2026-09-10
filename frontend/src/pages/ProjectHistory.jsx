import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, fmtBytes } from '../api.js'

export default function ProjectHistory() {
  const { id } = useParams()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .get(`/api/projects/${id}/history`)
      .then(setData)
      .catch((e) => setError(e.message))
  }, [id])

  if (error) return <div className="flash flash-err">{error}</div>
  if (!data) return <div className="muted">Cargando…</div>

  const p = data.project
  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="h1">{p.nombre}</h1>
          <p className="sub mono">{p.slug} · cuenta {p.account_nombre}</p>
        </div>
        <Link className="btn btn-ghost" to="/proyectos">Volver a proyectos</Link>
      </div>

      <div className="grid grid-stat">
        <div className="card stat">
          <div className="stat-ico" style={{ background: '#34d39922', color: '#34d399' }}>✓</div>
          <div><div className="stat-lbl">Backups OK</div><div className="stat-val">{data.stats?.backups_ok ?? 0}</div></div>
        </div>
        <div className="card stat">
          <div className="stat-ico" style={{ background: '#fb718522', color: '#fb7185' }}>!</div>
          <div><div className="stat-lbl">Errores</div><div className="stat-val">{data.stats?.backups_error ?? 0}</div></div>
        </div>
      </div>

      <div className="card">
        <div className="card-head"><span className="card-title">Historial de backups</span></div>
        <div className="table-scroll">
          <table className="t">
            <thead>
              <tr><th>Fecha</th><th>Resultado</th><th>Tamaño</th><th>Detalle</th></tr>
            </thead>
            <tbody>
              {(data.rows || []).map((r) => (
                <tr key={r.id}>
                  <td className="muted">{new Date(r.fecha).toLocaleString('es')}</td>
                  <td>
                    {r.resultado === 'ok' ? (
                      <span className="badge badge-ok">OK</span>
                    ) : (
                      <span className="badge badge-err">Error</span>
                    )}
                  </td>
                  <td className="mono">{fmtBytes(r.tamaño_archivo)}</td>
                  <td className="mono muted" style={{ wordBreak: 'break-all' }}>{r.detalle || r.ruta_archivo || '-'}</td>
                </tr>
              ))}
              {!data.rows?.length && (
                <tr className="empty"><td colSpan={4}>Sin backups todavía. El agendado los creará automáticamente.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}
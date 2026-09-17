import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { getProjectHistory } from '../../services/projects.js'
import { useAbort, isAbortError } from '../../hooks/useAbort.js'
import { fmtBytes, fmtFecha } from '../../utils/format.js'
import PageHead from '../../components/ui/PageHead.jsx'
import { useToast } from '../../components/ui/Toast.jsx'
import Badge from '../../components/ui/Badge.jsx'

export default function ProjectHistory() {
  const { id } = useParams()
  const toast = useToast()
  const signal = useAbort()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    getProjectHistory(id, { signal })
      .then(setData)
      .catch((e) => {
        if (!isAbortError(e)) setError(e.message)
      })
  }, [id])

  useEffect(() => {
    if (error) toast.err(error)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [error])

  if (error) return (
    <PageHead title="Historial" sub="No se pudo cargar el historial.">
      <Link className="btn btn-ghost" to="/proyectos">Volver a proyectos</Link>
    </PageHead>
  )
  if (!data) return <div className="muted">Cargando…</div>

  const p = data.project
  return (
    <>
      <PageHead title={p.nombre} sub={`${p.slug} · cuenta ${p.account_nombre}`} subClass="mono">
        <Link className="btn btn-ghost" to="/proyectos">Volver a proyectos</Link>
      </PageHead>

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
              <tr><th>Fecha</th><th>Estado</th><th>Tamaño</th><th>Detalle</th></tr>
            </thead>
            <tbody>
              {(data.rows || []).map((r) => (
                <tr key={r.id}>
                  <td className="muted">{fmtFecha(r.fecha)}</td>
                  <td>
                    {r.resultado === 'ok' ? (
                      <Badge tone="ok">OK</Badge>
                    ) : (
                      <Badge tone="err">Error</Badge>
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
import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api.js'

export default function Projects() {
  const [projects, setProjects] = useState([])
  const [error, setError] = useState('')
  const [params, setParams] = useSearchParams()
  const estado = params.get('estado') || 'activos'

  const load = () => {
    api
      .get(`/api/projects?estado=${estado}`)
      .then(setProjects)
      .catch((e) => setError(e.message))
  }

  useEffect(() => {
    setError('')
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [estado])

  const del = async (p) => {
    if (!window.confirm(`¿Eliminar el proyecto "${p.slug}"? Se conserva su historial.`)) return
    try {
      await api.del(`/api/projects/${p.id}`)
      load()
    } catch (e) {
      setError(e.message)
    }
  }

  const restore = async (p) => {
    const slug = window.prompt('Slug para restaurar:', p.slug.replace(/^\(eliminado\)-\d+-/, ''))
    if (slug == null) return
    try {
      await api.post(`/api/projects/${p.id}/restore`, { slug })
      load()
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="h1">Proyectos</h1>
          <p className="sub">Proyectos de Supabase configurados para respaldo.</p>
        </div>
        <div className="inline-actions">
          <Link className="btn btn-ghost" to={`/proyectos?estado=${estado === 'eliminados' ? 'activos' : 'eliminados'}`}>
            {estado === 'eliminados' ? 'Ver activos' : 'Ver eliminados'}
          </Link>
          <Link className="btn btn-primary" to="/proyectos/nuevo">Nuevo proyecto</Link>
        </div>
      </div>

      {error && <div className="flash flash-err">{error}</div>}

      <div className="card">
        <div className="table-scroll">
          <table className="t">
            <thead>
              <tr>
                <th>Slug</th>
                <th>Nombre</th>
                <th>Cuenta</th>
                <th>Ref</th>
                <th>Estado</th>
                <th className="td-actions">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {projects.map((p) => (
                <tr key={p.id}>
                  <td className="mono">{p.slug}</td>
                  <td>{p.nombre}</td>
                  <td className="muted">{p.account_nombre}</td>
                  <td className="mono muted">{p.project_ref ? p.project_ref.slice(0, 8) + '…' : '-'}</td>
                  <td>
                    {p.activo ? (
                      <span className="badge badge-ok">Activo</span>
                    ) : (
                      <span className="badge badge-mid">Eliminado</span>
                    )}
                  </td>
                  <td className="td-actions">
                    {p.activo ? (
                      <>
                        <Link className="btn-link" to={`/proyectos/${p.id}/historial`}>Historial</Link>
                        <Link className="btn-link" to={`/proyectos/${p.id}/editar`}>Editar</Link>
                        <button className="btn-link btn-link-danger" onClick={() => del(p)}>Eliminar</button>
                      </>
                    ) : (
                      <button className="btn-link" onClick={() => restore(p)}>Restaurar</button>
                    )}
                  </td>
                </tr>
              ))}
              {!projects.length && (
                <tr className="empty"><td colSpan={6}>No hay proyectos en esta vista.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}
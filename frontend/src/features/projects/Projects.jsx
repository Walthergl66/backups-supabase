import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { deleteProject, listProjects, restoreProject } from '../../services/projects.js'
import PageHead from '../../components/ui/PageHead.jsx'
import Flash from '../../components/ui/Flash.jsx'
import Badge from '../../components/ui/Badge.jsx'

export default function Projects() {
  const [projects, setProjects] = useState([])
  const [error, setError] = useState('')
  const [params, setParams] = useSearchParams()
  const estado = params.get('estado') || 'activos'

  const load = () => {
    listProjects(estado)
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
      await deleteProject(p.id)
      load()
    } catch (e) {
      setError(e.message)
    }
  }

  const restore = async (p) => {
    const slug = window.prompt('Slug para restaurar:', p.slug.replace(/^\(eliminado\)-\d+-/, ''))
    if (slug == null) return
    try {
      await restoreProject(p.id, slug)
      load()
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <>
      <PageHead title="Proyectos" sub="Proyectos de Supabase configurados para respaldo.">
        <div className="inline-actions">
          <Link className="btn btn-ghost" to={`/proyectos?estado=${estado === 'eliminados' ? 'activos' : 'eliminados'}`}>
            {estado === 'eliminados' ? 'Ver activos' : 'Ver eliminados'}
          </Link>
          <Link className="btn btn-primary" to="/proyectos/nuevo">Nuevo proyecto</Link>
        </div>
      </PageHead>

      {error && <Flash type="err">{error}</Flash>}

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
                      <Badge tone="ok">Activo</Badge>
                    ) : (
                      <Badge tone="mid">Eliminado</Badge>
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
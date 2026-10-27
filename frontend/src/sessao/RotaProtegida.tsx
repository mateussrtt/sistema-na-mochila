import { Navigate, Outlet, useLocation } from 'react-router'

import { useSessao } from './contexto'

/** Só mostra as telas para quem entrou. Quem não entrou vai para a tela de login. */
export default function RotaProtegida() {
  const { usuario, conferindo } = useSessao()
  const local = useLocation()

  if (conferindo) {
    return (
      <div className="abertura" role="status">
        <span className="marca-selo" aria-hidden="true">
          NM
        </span>
        <span>Abrindo o sistema…</span>
      </div>
    )
  }
  if (!usuario) {
    return <Navigate to="/entrar" replace state={{ voltarPara: local.pathname }} />
  }
  return <Outlet />
}

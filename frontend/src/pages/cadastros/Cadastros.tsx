import { useEffect, useRef } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router'

export default function Cadastros() {
  const { pathname } = useLocation()
  const abas = useRef<HTMLElement>(null)

  // Em telas muito estreitas as abas rolam dentro da barra: a aba aberta precisa estar à vista
  useEffect(() => {
    abas.current
      ?.querySelector<HTMLElement>('a.active')
      ?.scrollIntoView({ block: 'nearest', inline: 'nearest' })
  }, [pathname])

  return (
    <section className="pagina">
      <header className="pagina-cabecalho">
        <h1>Alunos e matrículas</h1>
        <p>
          Cadastre os alunos, vincule quem responde por cada um, matricule-os definindo a
          mensalidade e registre as empresas que apadrinham alunos.
        </p>
      </header>

      <nav className="abas" aria-label="Cadastros" ref={abas}>
        <NavLink to="/alunos" end>
          Alunos
        </NavLink>
        <NavLink to="/alunos/responsaveis">Responsáveis</NavLink>
        <NavLink to="/alunos/matriculas">Matrículas</NavLink>
        <NavLink to="/alunos/padrinhos">Padrinhos</NavLink>
      </nav>

      <Outlet />
    </section>
  )
}

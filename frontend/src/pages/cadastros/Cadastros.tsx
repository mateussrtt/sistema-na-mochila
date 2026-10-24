import { NavLink, Outlet } from 'react-router'

export default function Cadastros() {
  return (
    <section className="pagina">
      <header className="pagina-cabecalho">
        <h1>Alunos e matrículas</h1>
        <p>
          Cadastre os alunos, vincule quem responde por cada um e matricule-os definindo a
          mensalidade.
        </p>
      </header>

      <nav className="abas" aria-label="Cadastros">
        <NavLink to="/alunos" end>
          Alunos
        </NavLink>
        <NavLink to="/alunos/responsaveis">Responsáveis</NavLink>
        <NavLink to="/alunos/matriculas">Matrículas</NavLink>
      </nav>

      <Outlet />
    </section>
  )
}

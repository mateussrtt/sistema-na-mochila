  import { NavLink, Outlet } from 'react-router'

const menu = [
  { to: '/', rotulo: 'Início' },
  { to: '/alunos', rotulo: 'Alunos' },
  { to: '/mensalidades', rotulo: 'Mensalidades' },
  { to: '/despesas', rotulo: 'Despesas' },
  { to: '/receitas', rotulo: 'Receitas' },
  { to: '/caixa', rotulo: 'Caixa' },
]

export default function Layout() {
  return (
    <div className="app">
      <header className="topo">
        <span className="marca">Na Mochila</span>
        <nav className="menu">
          {menu.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.to === '/'}>
              {item.rotulo}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="conteudo">
        <Outlet />
      </main>
    </div>
  )
}

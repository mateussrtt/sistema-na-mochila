import {
  ChartNoAxesColumn,
  HandCoins,
  House,
  Menu,
  ReceiptText,
  TrendingDown,
  Users,
  X,
} from 'lucide-react'
import { useState } from 'react'
import { NavLink, Outlet } from 'react-router'

const menu = [
  { to: '/', rotulo: 'Início', Icone: House },
  { to: '/alunos', rotulo: 'Alunos', Icone: Users },
  { to: '/mensalidades', rotulo: 'Mensalidades', Icone: ReceiptText },
  { to: '/despesas', rotulo: 'Despesas', Icone: TrendingDown },
  { to: '/receitas', rotulo: 'Receitas', Icone: HandCoins },
  { to: '/caixa', rotulo: 'Caixa', Icone: ChartNoAxesColumn },
]

export default function Layout() {
  const [menuAberto, setMenuAberto] = useState(false)

  return (
    <div className="app">
      <aside className={`lateral${menuAberto ? ' aberta' : ''}`}>
        <div className="lateral-topo">
          <NavLink to="/" className="marca" onClick={() => setMenuAberto(false)}>
            <span className="marca-selo" aria-hidden="true">
              NM
            </span>
            <span className="marca-texto">
              <strong>Na Mochila</strong>
              <span>Gestão financeira</span>
            </span>
          </NavLink>
          <button
            type="button"
            className="botao-menu"
            aria-label={menuAberto ? 'Fechar menu' : 'Abrir menu'}
            aria-expanded={menuAberto}
            aria-controls="menu-principal"
            onClick={() => setMenuAberto((aberto) => !aberto)}
          >
            {menuAberto ? <X size={22} /> : <Menu size={22} />}
          </button>
        </div>

        <nav id="menu-principal" className="menu" aria-label="Menu principal">
          {menu.map(({ to, rotulo, Icone }) => (
            <NavLink key={to} to={to} end={to === '/'} onClick={() => setMenuAberto(false)}>
              <Icone size={19} strokeWidth={1.8} aria-hidden="true" />
              {rotulo}
            </NavLink>
          ))}
        </nav>

        <p className="lateral-rodape">Robótica educacional no Médio Piracicaba</p>
      </aside>

      <main className="conteudo">
        <Outlet />
      </main>
    </div>
  )
}

import {
  ChartNoAxesColumn,
  HandCoins,
  House,
  KeyRound,
  LogOut,
  Menu,
  ReceiptText,
  ShieldCheck,
  TrendingDown,
  Users,
  X,
} from 'lucide-react'
import { useCallback, useState } from 'react'
import { NavLink, Outlet } from 'react-router'

import { NOME_DO_PERFIL } from '../api/auth'
import FormMinhaSenha from '../pages/usuarios/FormMinhaSenha'
import { useSessao } from '../sessao/contexto'
import Aviso from './Aviso'
import Gaveta from './Gaveta'
import Monograma from './Monograma'

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
  const [trocandoSenha, setTrocandoSenha] = useState(false)
  const [aviso, setAviso] = useState<string | null>(null)
  const { usuario, ehAdmin, sair } = useSessao()
  const fecharAviso = useCallback(() => setAviso(null), [])

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
          {ehAdmin && (
            <>
              <p className="menu-secao">Administração</p>
              <NavLink to="/usuarios" onClick={() => setMenuAberto(false)}>
                <ShieldCheck size={19} strokeWidth={1.8} aria-hidden="true" />
                Usuários
              </NavLink>
            </>
          )}
        </nav>

        {usuario && (
          <div className="lateral-usuario">
            <div className="lateral-pessoa">
              <Monograma nome={usuario.nome} tamanho="p" />
              <span className="pessoa-texto">
                <strong>{usuario.nome}</strong>
                <span>{NOME_DO_PERFIL[usuario.perfil]}</span>
              </span>
            </div>
            <div className="lateral-acoes">
              <button
                type="button"
                className="lateral-acao"
                onClick={() => {
                  setMenuAberto(false)
                  setTrocandoSenha(true)
                }}
              >
                <KeyRound size={16} aria-hidden="true" />
                Trocar senha
              </button>
              <button type="button" className="lateral-acao" onClick={sair}>
                <LogOut size={16} aria-hidden="true" />
                Sair
              </button>
            </div>
          </div>
        )}
      </aside>

      <main className="conteudo">
        <Outlet />
      </main>

      <Gaveta
        aberta={trocandoSenha}
        titulo="Trocar minha senha"
        descricao="Depois de trocar, use a nova senha no próximo acesso."
        aoFechar={() => setTrocandoSenha(false)}
      >
        <FormMinhaSenha
          aoCancelar={() => setTrocandoSenha(false)}
          aoSalvar={() => {
            setTrocandoSenha(false)
            setAviso('Senha trocada')
          }}
        />
      </Gaveta>
      <Aviso mensagem={aviso} aoSumir={fecharAviso} />
    </div>
  )
}

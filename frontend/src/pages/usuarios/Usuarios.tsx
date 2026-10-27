import { ChevronRight, Mail, Plus, ShieldCheck } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router'

import { NOME_DO_PERFIL, type Usuario } from '../../api/auth'
import { listarUsuarios } from '../../api/usuarios'
import Aviso from '../../components/Aviso'
import { Carregando, FalhaAoCarregar } from '../../components/EstadoLista'
import Gaveta from '../../components/Gaveta'
import Monograma from '../../components/Monograma'
import { useSessao } from '../../sessao/contexto'
import { plural } from '../../utils/formato'
import FormUsuario from './FormUsuario'

type Gaveta = { modo: 'novo' } | { modo: 'editar'; usuario: Usuario } | null

function resumo(usuarios: Usuario[]): string {
  const desativados = usuarios.filter((u) => !u.ativo).length
  const total = plural(usuarios.length - desativados, 'usuário ativo', 'usuários ativos')
  return desativados > 0 ? `${total} · ${plural(desativados, 'desativado', 'desativados')}` : total
}

export default function Usuarios() {
  const { usuario: logado, ehAdmin, atualizarUsuario } = useSessao()
  const [usuarios, setUsuarios] = useState<Usuario[] | null>(null)
  const [falhou, setFalhou] = useState(false)
  const [versao, setVersao] = useState(0)
  const [gaveta, setGaveta] = useState<Gaveta>(null)
  const [aviso, setAviso] = useState<string | null>(null)

  useEffect(() => {
    if (!ehAdmin) return
    const controle = new AbortController()
    listarUsuarios(controle.signal)
      .then((lista) => {
        setUsuarios(lista)
        setFalhou(false)
      })
      .catch(() => {
        if (!controle.signal.aborted) setFalhou(true)
      })
    return () => controle.abort()
  }, [ehAdmin, versao])

  const fecharAviso = useCallback(() => setAviso(null), [])

  if (!ehAdmin) {
    return (
      <section className="pagina">
        <div className="estado">
          <ShieldCheck size={28} aria-hidden="true" />
          <h3>Só o administrador acessa esta tela</h3>
          <p>Se precisar de um acesso novo ou de outra senha, fale com a coordenação.</p>
          <Link to="/" className="botao botao-secundario">
            Voltar para o início
          </Link>
        </div>
      </section>
    )
  }

  function recarregar() {
    setFalhou(false)
    setVersao((v) => v + 1)
  }

  function aoSalvar(salvo: Usuario, mensagem: string) {
    if (salvo.id === logado?.id) atualizarUsuario(salvo)
    setGaveta(null)
    setAviso(mensagem)
    recarregar()
  }

  const editando = gaveta?.modo === 'editar' ? gaveta.usuario : undefined

  return (
    <section className="pagina">
      <header className="pagina-cabecalho">
        <h1>Usuários e acessos</h1>
        <p>Quem pode entrar no sistema e o que cada pessoa pode fazer.</p>
      </header>

      <div className="barra barra-direita">
        <button
          type="button"
          className="botao botao-principal botao-com-icone"
          onClick={() => setGaveta({ modo: 'novo' })}
        >
          <Plus size={18} aria-hidden="true" />
          Cadastrar usuário
        </button>
      </div>

      {falhou ? (
        <FalhaAoCarregar oQue="os usuários" aoTentar={recarregar} />
      ) : usuarios === null ? (
        <Carregando linhas={3} />
      ) : (
        <>
          <p className="resumo">{resumo(usuarios)}</p>
          <ul className="lista">
            {usuarios.map((u) => (
              <li key={u.id}>
                <button
                  type="button"
                  className="linha"
                  onClick={() => setGaveta({ modo: 'editar', usuario: u })}
                >
                  <Monograma nome={u.nome} apagado={!u.ativo} />
                  <span className="linha-principal">
                    <span className="linha-titulo">
                      {u.nome}
                      {u.id === logado?.id && <span className="etiqueta etiqueta-voce">Você</span>}
                      {!u.ativo && <span className="etiqueta">Sem acesso</span>}
                    </span>
                    <span className="linha-detalhes">
                      <span>
                        <Mail size={14} aria-hidden="true" />
                        {u.email}
                      </span>
                    </span>
                  </span>
                  <span className="linha-lateral">
                    <span className="linha-rotulo">Perfil</span>
                    <span>{NOME_DO_PERFIL[u.perfil]}</span>
                  </span>
                  <ChevronRight size={18} className="linha-seta" aria-hidden="true" />
                </button>
              </li>
            ))}
          </ul>
        </>
      )}

      <Gaveta
        aberta={gaveta !== null}
        titulo={editando ? editando.nome : 'Cadastrar usuário'}
        descricao={
          editando
            ? editando.ativo
              ? 'Altere os dados, o perfil ou a senha de acesso.'
              : 'Este usuário está sem acesso. Reative para ele voltar a entrar.'
            : 'A pessoa entra com este e-mail e a senha inicial.'
        }
        aoFechar={() => setGaveta(null)}
      >
        <FormUsuario
          key={editando?.id ?? 'novo'}
          usuario={editando}
          aoCancelar={() => setGaveta(null)}
          aoSalvar={aoSalvar}
        />
      </Gaveta>

      <Aviso mensagem={aviso} aoSumir={fecharAviso} />
    </section>
  )
}

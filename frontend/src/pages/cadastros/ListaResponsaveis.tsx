import { ChevronRight, Mail, Phone, Plus } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

import { listarResponsaveis, type Responsavel } from '../../api/cadastros'
import Aviso from '../../components/Aviso'
import Busca from '../../components/Busca'
import { Carregando, FalhaAoCarregar, Vazio } from '../../components/EstadoLista'
import Gaveta from '../../components/Gaveta'
import Monograma from '../../components/Monograma'
import { useAtraso } from '../../hooks/useAtraso'
import { plural } from '../../utils/formato'
import FormResponsavel from './FormResponsavel'

type Gaveta = { modo: 'novo' } | { modo: 'editar'; responsavel: Responsavel } | null

export default function ListaResponsaveis() {
  const [busca, setBusca] = useState('')
  const [responsaveis, setResponsaveis] = useState<Responsavel[] | null>(null)
  const [falhou, setFalhou] = useState(false)
  const [versao, setVersao] = useState(0)
  const [gaveta, setGaveta] = useState<Gaveta>(null)
  const [aviso, setAviso] = useState<string | null>(null)
  const buscaAtrasada = useAtraso(busca.trim())

  useEffect(() => {
    const controle = new AbortController()
    listarResponsaveis(buscaAtrasada, controle.signal)
      .then((lista) => {
        setResponsaveis(lista)
        setFalhou(false)
      })
      .catch(() => {
        if (!controle.signal.aborted) setFalhou(true)
      })
    return () => controle.abort()
  }, [buscaAtrasada, versao])

  function recarregar() {
    setFalhou(false)
    setVersao((v) => v + 1)
  }
  const fecharAviso = useCallback(() => setAviso(null), [])

  return (
    <>
      <div className="barra">
        <Busca
          id="busca-responsaveis"
          rotulo="Buscar responsáveis"
          valor={busca}
          aoMudar={setBusca}
          placeholder="Buscar responsável pelo nome"
        />
        <button
          type="button"
          className="botao botao-principal botao-com-icone"
          onClick={() => setGaveta({ modo: 'novo' })}
        >
          <Plus size={18} aria-hidden="true" />
          Cadastrar responsável
        </button>
      </div>

      {falhou ? (
        <FalhaAoCarregar oQue="os responsáveis" aoTentar={recarregar} />
      ) : responsaveis === null ? (
        <Carregando />
      ) : responsaveis.length === 0 ? (
        buscaAtrasada ? (
          <Vazio
            titulo={`Nenhum responsável encontrado para “${buscaAtrasada}”`}
            texto="Confira a grafia do nome."
          />
        ) : (
          <Vazio
            titulo="Nenhum responsável cadastrado"
            texto="Você também pode cadastrar o responsável direto no cadastro do aluno."
          />
        )
      ) : (
        <>
          <p className="resumo">
            {plural(responsaveis.length, 'responsável', 'responsáveis')}
            {buscaAtrasada && ` para “${buscaAtrasada}”`}
          </p>
          <ul className="lista">
            {responsaveis.map((r) => (
              <li key={r.id}>
                <button
                  type="button"
                  className="linha linha-simples"
                  onClick={() => setGaveta({ modo: 'editar', responsavel: r })}
                >
                  <Monograma nome={r.nome} />
                  <span className="linha-principal">
                    <span className="linha-titulo">{r.nome}</span>
                    <span className="linha-detalhes">
                      {r.telefone && (
                        <span>
                          <Phone size={14} aria-hidden="true" />
                          {r.telefone}
                        </span>
                      )}
                      {r.email && (
                        <span>
                          <Mail size={14} aria-hidden="true" />
                          {r.email}
                        </span>
                      )}
                    </span>
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
        titulo={gaveta?.modo === 'editar' ? gaveta.responsavel.nome : 'Cadastrar responsável'}
        descricao="Informe ao menos um contato: telefone ou e-mail."
        aoFechar={() => setGaveta(null)}
      >
        <FormResponsavel
          key={gaveta?.modo === 'editar' ? gaveta.responsavel.id : 'novo'}
          responsavel={gaveta?.modo === 'editar' ? gaveta.responsavel : undefined}
          aoCancelar={() => setGaveta(null)}
          aoSalvar={() => {
            setAviso(gaveta?.modo === 'editar' ? 'Alterações salvas' : 'Responsável cadastrado')
            setGaveta(null)
            recarregar()
          }}
        />
      </Gaveta>

      <Aviso mensagem={aviso} aoSumir={fecharAviso} />
    </>
  )
}

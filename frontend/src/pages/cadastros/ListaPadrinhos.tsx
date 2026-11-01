import { Building2, ChevronRight, GraduationCap, Phone, Plus, UserRound } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

import type { Situacao } from '../../api/cadastros'
import { listarPadrinhos, type Padrinho } from '../../api/padrinhos'
import Aviso from '../../components/Aviso'
import Busca from '../../components/Busca'
import { Carregando, FalhaAoCarregar, Vazio } from '../../components/EstadoLista'
import Gaveta from '../../components/Gaveta'
import Monograma from '../../components/Monograma'
import { useAtraso } from '../../hooks/useAtraso'
import { useSessao } from '../../sessao/contexto'
import { mascaraCnpj, mascaraTelefone, plural } from '../../utils/formato'
import FormPadrinho from './FormPadrinho'

const SITUACOES: { valor: Situacao; rotulo: string }[] = [
  { valor: 'ativos', rotulo: 'Ativos' },
  { valor: 'inativos', rotulo: 'Inativos' },
  { valor: 'todos', rotulo: 'Todos' },
]

type Gaveta = { modo: 'novo' } | { modo: 'editar'; padrinho: Padrinho } | null

function resumo(total: number, situacao: Situacao, busca: string): string {
  const padrinhos = plural(total, 'padrinho', 'padrinhos')
  const sufixo = total === 1 ? '' : 's'
  const filtro = { ativos: ` ativo${sufixo}`, inativos: ` inativo${sufixo}`, todos: '' }[situacao]
  return busca ? `${padrinhos}${filtro} para “${busca}”` : `${padrinhos}${filtro}`
}

export default function ListaPadrinhos() {
  const [busca, setBusca] = useState('')
  const [situacao, setSituacao] = useState<Situacao>('ativos')
  const [padrinhos, setPadrinhos] = useState<Padrinho[] | null>(null)
  const [falhou, setFalhou] = useState(false)
  const [versao, setVersao] = useState(0)
  const [gaveta, setGaveta] = useState<Gaveta>(null)
  const [aviso, setAviso] = useState<string | null>(null)
  const buscaAtrasada = useAtraso(busca.trim())
  const { podeEditar } = useSessao()

  useEffect(() => {
    const controle = new AbortController()
    listarPadrinhos(buscaAtrasada, situacao, controle.signal)
      .then((lista) => {
        setPadrinhos(lista)
        setFalhou(false)
      })
      .catch(() => {
        if (!controle.signal.aborted) setFalhou(true)
      })
    return () => controle.abort()
  }, [buscaAtrasada, situacao, versao])

  function recarregar() {
    setFalhou(false)
    setVersao((v) => v + 1)
  }
  const fecharAviso = useCallback(() => setAviso(null), [])

  function aoSalvar(mensagem: string) {
    setGaveta(null)
    setAviso(mensagem)
    recarregar()
  }

  const botaoNovo = podeEditar && (
    <button
      type="button"
      className="botao botao-principal botao-com-icone"
      onClick={() => setGaveta({ modo: 'novo' })}
    >
      <Plus size={18} aria-hidden="true" />
      Cadastrar padrinho
    </button>
  )

  return (
    <>
      <div className="barra">
        <Busca
          id="busca-padrinhos"
          rotulo="Buscar padrinhos"
          valor={busca}
          aoMudar={setBusca}
          placeholder="Buscar por empresa ou contato"
        />
        <div className="segmentos" role="group" aria-label="Situação">
          {SITUACOES.map((s) => (
            <button
              key={s.valor}
              type="button"
              aria-pressed={situacao === s.valor}
              onClick={() => setSituacao(s.valor)}
            >
              {s.rotulo}
            </button>
          ))}
        </div>
        {botaoNovo}
      </div>

      {falhou ? (
        <FalhaAoCarregar oQue="os padrinhos" aoTentar={recarregar} />
      ) : padrinhos === null ? (
        <Carregando />
      ) : padrinhos.length === 0 ? (
        buscaAtrasada ? (
          <Vazio
            titulo={`Nenhum padrinho encontrado para “${buscaAtrasada}”`}
            texto="Confira a grafia do nome da empresa ou da pessoa de contato."
          />
        ) : situacao === 'ativos' ? (
          <Vazio
            titulo="Nenhum padrinho ativo ainda"
            texto="Cadastre as empresas que apadrinham alunos, com o vencimento combinado com cada uma."
          >
            {botaoNovo}
          </Vazio>
        ) : (
          <Vazio titulo="Nenhum padrinho inativo" texto="Padrinhos inativados aparecem aqui." />
        )
      ) : (
        <>
          <p className="resumo">{resumo(padrinhos.length, situacao, buscaAtrasada)}</p>
          <ul className="lista">
            {padrinhos.map((padrinho) => (
              <li key={padrinho.id}>
                <button
                  type="button"
                  className="linha"
                  onClick={() => setGaveta({ modo: 'editar', padrinho })}
                >
                  <Monograma nome={padrinho.nome} apagado={!padrinho.ativo} />
                  <span className="linha-principal">
                    <span className="linha-titulo">
                      {padrinho.nome}
                      {!padrinho.ativo && <span className="etiqueta">Inativo</span>}
                    </span>
                    <span className="linha-detalhes">
                      {padrinho.cnpj && (
                        <span>
                          <Building2 size={14} aria-hidden="true" />
                          {mascaraCnpj(padrinho.cnpj)}
                        </span>
                      )}
                      {padrinho.contato && (
                        <span>
                          <UserRound size={14} aria-hidden="true" />
                          {padrinho.contato}
                        </span>
                      )}
                      <span>
                        <Phone size={14} aria-hidden="true" />
                        {mascaraTelefone(padrinho.telefone)}
                      </span>
                      {padrinho.alunos_apadrinhados > 0 && (
                        <span>
                          <GraduationCap size={14} aria-hidden="true" />
                          {plural(padrinho.alunos_apadrinhados, 'aluno apadrinhado', 'alunos apadrinhados')}
                        </span>
                      )}
                    </span>
                  </span>
                  <span className="linha-lateral">
                    <span className="linha-rotulo">Vencimento</span>
                    <span>
                      Dia {padrinho.dia_vencimento}
                      {padrinho.emitir_ate_dia && (
                        <span className="mais"> · nota até o dia {padrinho.emitir_ate_dia}</span>
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
        titulo={gaveta?.modo === 'editar' ? gaveta.padrinho.nome : 'Cadastrar padrinho'}
        descricao={
          !podeEditar
            ? 'Seu perfil pode consultar os dados, mas não alterar.'
            : gaveta?.modo === 'editar'
              ? 'Edite os dados ou o vencimento combinado com a empresa.'
              : 'Empresa que paga a mensalidade de alunos, com o vencimento combinado.'
        }
        aoFechar={() => setGaveta(null)}
      >
        <FormPadrinho
          key={gaveta?.modo === 'editar' ? gaveta.padrinho.id : 'novo'}
          padrinho={gaveta?.modo === 'editar' ? gaveta.padrinho : undefined}
          aoSalvar={aoSalvar}
          aoCancelar={() => setGaveta(null)}
        />
      </Gaveta>

      <Aviso mensagem={aviso} aoSumir={fecharAviso} />
    </>
  )
}

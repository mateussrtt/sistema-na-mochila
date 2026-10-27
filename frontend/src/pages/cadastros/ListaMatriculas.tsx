import { CalendarDays, ChevronRight, Plus } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

import { listarMatriculas, type Matricula, type SituacaoMatricula } from '../../api/cadastros'
import Aviso from '../../components/Aviso'
import Busca from '../../components/Busca'
import { Carregando, FalhaAoCarregar, Vazio } from '../../components/EstadoLista'
import Gaveta from '../../components/Gaveta'
import Monograma from '../../components/Monograma'
import { useAtraso } from '../../hooks/useAtraso'
import { useSessao } from '../../sessao/contexto'
import { formatarData, formatarMoeda, plural } from '../../utils/formato'
import DetalheMatricula from './DetalheMatricula'
import FormMatricula from './FormMatricula'

const SITUACOES: { valor: SituacaoMatricula; rotulo: string }[] = [
  { valor: 'ativas', rotulo: 'Ativas' },
  { valor: 'encerradas', rotulo: 'Encerradas' },
  { valor: 'todas', rotulo: 'Todas' },
]

type Gaveta = { modo: 'nova' } | { modo: 'detalhe'; matricula: Matricula } | null

function resumo(total: number, situacao: SituacaoMatricula, busca: string): string {
  const matriculas = plural(total, 'matrícula', 'matrículas')
  const sufixo = total === 1 ? '' : 's'
  const filtro = { ativas: ` ativa${sufixo}`, encerradas: ` encerrada${sufixo}`, todas: '' }[
    situacao
  ]
  return busca ? `${matriculas}${filtro} para “${busca}”` : `${matriculas}${filtro}`
}

export default function ListaMatriculas() {
  const [busca, setBusca] = useState('')
  const [situacao, setSituacao] = useState<SituacaoMatricula>('ativas')
  const [matriculas, setMatriculas] = useState<Matricula[] | null>(null)
  const [falhou, setFalhou] = useState(false)
  const [versao, setVersao] = useState(0)
  const [gaveta, setGaveta] = useState<Gaveta>(null)
  const [aviso, setAviso] = useState<string | null>(null)
  const buscaAtrasada = useAtraso(busca.trim())
  const { podeEditar } = useSessao()

  useEffect(() => {
    const controle = new AbortController()
    listarMatriculas(buscaAtrasada, situacao, controle.signal)
      .then((lista) => {
        setMatriculas(lista)
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

  return (
    <>
      <div className="barra">
        <Busca
          id="busca-matriculas"
          rotulo="Buscar matrículas"
          valor={busca}
          aoMudar={setBusca}
          placeholder="Buscar matrícula pelo nome do aluno"
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
        {podeEditar && (
          <button
            type="button"
            className="botao botao-principal botao-com-icone"
            onClick={() => setGaveta({ modo: 'nova' })}
          >
            <Plus size={18} aria-hidden="true" />
            Nova matrícula
          </button>
        )}
      </div>

      {falhou ? (
        <FalhaAoCarregar oQue="as matrículas" aoTentar={recarregar} />
      ) : matriculas === null ? (
        <Carregando />
      ) : matriculas.length === 0 ? (
        buscaAtrasada ? (
          <Vazio
            titulo={`Nenhuma matrícula encontrada para “${buscaAtrasada}”`}
            texto="Confira a grafia do nome do aluno."
          />
        ) : situacao === 'encerradas' ? (
          <Vazio
            titulo="Nenhuma matrícula encerrada"
            texto="Matrículas encerradas aparecem aqui, com o histórico preservado."
          />
        ) : (
          <Vazio
            titulo="Nenhuma matrícula ainda"
            texto="Matricule um aluno e defina o valor da mensalidade para que ela passe a ser cobrada."
          >
            {podeEditar && (
              <button
                type="button"
                className="botao botao-principal botao-com-icone"
                onClick={() => setGaveta({ modo: 'nova' })}
              >
                <Plus size={18} aria-hidden="true" />
                Nova matrícula
              </button>
            )}
          </Vazio>
        )
      ) : (
        <>
          <p className="resumo">{resumo(matriculas.length, situacao, buscaAtrasada)}</p>
          <ul className="lista">
            {matriculas.map((matricula) => {
              const encerrada = matricula.situacao === 'encerrada'
              return (
                <li key={matricula.id}>
                  <button
                    type="button"
                    className="linha"
                    onClick={() => setGaveta({ modo: 'detalhe', matricula })}
                  >
                    <Monograma nome={matricula.aluno.nome} apagado={encerrada} />
                    <span className="linha-principal">
                      <span className="linha-titulo">
                        {matricula.aluno.nome}
                        {encerrada && <span className="etiqueta">Encerrada</span>}
                      </span>
                      <span className="linha-detalhes">
                        <span>
                          <CalendarDays size={14} aria-hidden="true" />
                          {encerrada && matricula.data_encerramento
                            ? `${formatarData(matricula.data_inicio)} a ${formatarData(matricula.data_encerramento)}`
                            : `Desde ${formatarData(matricula.data_inicio)}`}
                        </span>
                      </span>
                    </span>
                    <span className="linha-lateral">
                      <span className="linha-rotulo">Mensalidade</span>
                      <span>{formatarMoeda(matricula.valor_mensalidade)}</span>
                    </span>
                    <ChevronRight size={18} className="linha-seta" aria-hidden="true" />
                  </button>
                </li>
              )
            })}
          </ul>
        </>
      )}

      <Gaveta
        aberta={gaveta !== null}
        titulo={gaveta?.modo === 'detalhe' ? gaveta.matricula.aluno.nome : 'Nova matrícula'}
        descricao={
          gaveta?.modo !== 'detalhe'
            ? 'Escolha o aluno e defina o valor da mensalidade.'
            : podeEditar
              ? 'Dados da matrícula e encerramento.'
              : 'Dados da matrícula. Seu perfil pode consultar, mas não alterar.'
        }
        aoFechar={() => setGaveta(null)}
      >
        {gaveta?.modo === 'detalhe' ? (
          <DetalheMatricula
            key={gaveta.matricula.id}
            matricula={gaveta.matricula}
            aoEncerrar={aoSalvar}
            aoFechar={() => setGaveta(null)}
          />
        ) : (
          <FormMatricula aoSalvar={aoSalvar} aoCancelar={() => setGaveta(null)} />
        )}
      </Gaveta>

      <Aviso mensagem={aviso} aoSumir={fecharAviso} />
    </>
  )
}

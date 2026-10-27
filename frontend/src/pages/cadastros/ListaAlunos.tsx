import { Cake, ChevronRight, MapPin, Plus, School } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

import { listarAlunos, type Aluno, type Situacao } from '../../api/cadastros'
import Aviso from '../../components/Aviso'
import Busca from '../../components/Busca'
import { Carregando, FalhaAoCarregar, Vazio } from '../../components/EstadoLista'
import Gaveta from '../../components/Gaveta'
import Monograma from '../../components/Monograma'
import { useAtraso } from '../../hooks/useAtraso'
import { useSessao } from '../../sessao/contexto'
import { idade, plural } from '../../utils/formato'
import FormAluno from './FormAluno'

const SITUACOES: { valor: Situacao; rotulo: string }[] = [
  { valor: 'ativos', rotulo: 'Ativos' },
  { valor: 'inativos', rotulo: 'Inativos' },
  { valor: 'todos', rotulo: 'Todos' },
]

type Gaveta = { modo: 'novo' } | { modo: 'editar'; aluno: Aluno } | null

function resumo(total: number, situacao: Situacao, busca: string): string {
  const alunos = plural(total, 'aluno', 'alunos')
  const sufixo = total === 1 ? '' : 's'
  const filtro = { ativos: ` ativo${sufixo}`, inativos: ` inativo${sufixo}`, todos: '' }[situacao]
  return busca ? `${alunos}${filtro} para “${busca}”` : `${alunos}${filtro}`
}

export default function ListaAlunos() {
  const [busca, setBusca] = useState('')
  const [situacao, setSituacao] = useState<Situacao>('ativos')
  const [alunos, setAlunos] = useState<Aluno[] | null>(null)
  const [falhou, setFalhou] = useState(false)
  const [versao, setVersao] = useState(0)
  const [gaveta, setGaveta] = useState<Gaveta>(null)
  const [aviso, setAviso] = useState<string | null>(null)
  const buscaAtrasada = useAtraso(busca.trim())
  const { podeEditar } = useSessao()

  useEffect(() => {
    const controle = new AbortController()
    listarAlunos(buscaAtrasada, situacao, controle.signal)
      .then((lista) => {
        setAlunos(lista)
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
          id="busca-alunos"
          rotulo="Buscar alunos"
          valor={busca}
          aoMudar={setBusca}
          placeholder="Buscar por aluno ou responsável"
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
            onClick={() => setGaveta({ modo: 'novo' })}
          >
            <Plus size={18} aria-hidden="true" />
            Cadastrar aluno
          </button>
        )}
      </div>

      {falhou ? (
        <FalhaAoCarregar oQue="os alunos" aoTentar={recarregar} />
      ) : alunos === null ? (
        <Carregando />
      ) : alunos.length === 0 ? (
        buscaAtrasada ? (
          <Vazio
            titulo={`Nenhum aluno encontrado para “${buscaAtrasada}”`}
            texto="Confira a grafia ou busque pelo nome de um responsável."
          />
        ) : situacao === 'ativos' ? (
          <Vazio
            titulo="Nenhum aluno ativo ainda"
            texto="Cadastre o primeiro aluno e vincule os responsáveis por ele."
          >
            {podeEditar && (
              <button
                type="button"
                className="botao botao-principal botao-com-icone"
                onClick={() => setGaveta({ modo: 'novo' })}
              >
                <Plus size={18} aria-hidden="true" />
                Cadastrar aluno
              </button>
            )}
          </Vazio>
        ) : (
          <Vazio titulo="Nenhum aluno inativo" texto="Alunos inativados aparecem aqui." />
        )
      ) : (
        <>
          <p className="resumo">{resumo(alunos.length, situacao, buscaAtrasada)}</p>
          <ul className="lista">
            {alunos.map((aluno) => (
              <li key={aluno.id}>
                <button
                  type="button"
                  className="linha"
                  onClick={() => setGaveta({ modo: 'editar', aluno })}
                >
                  <Monograma nome={aluno.nome} apagado={!aluno.ativo} />
                  <span className="linha-principal">
                    <span className="linha-titulo">
                      {aluno.nome}
                      {!aluno.ativo && <span className="etiqueta">Inativo</span>}
                    </span>
                    <span className="linha-detalhes">
                      {aluno.escola && (
                        <span>
                          <School size={14} aria-hidden="true" />
                          {aluno.escola}
                        </span>
                      )}
                      {aluno.municipio && (
                        <span>
                          <MapPin size={14} aria-hidden="true" />
                          {aluno.municipio}
                        </span>
                      )}
                      {aluno.data_nascimento && (
                        <span>
                          <Cake size={14} aria-hidden="true" />
                          {idade(aluno.data_nascimento)} anos
                        </span>
                      )}
                    </span>
                  </span>
                  <span className="linha-lateral">
                    <span className="linha-rotulo">
                      {aluno.responsaveis.length > 1 ? 'Responsáveis' : 'Responsável'}
                    </span>
                    <span>
                      {aluno.responsaveis[0]?.nome}
                      {aluno.responsaveis.length > 1 && (
                        <span className="mais"> e mais {aluno.responsaveis.length - 1}</span>
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
        titulo={gaveta?.modo === 'editar' ? gaveta.aluno.nome : 'Cadastrar aluno'}
        descricao={
          !podeEditar
            ? 'Seu perfil pode consultar os dados, mas não alterar.'
            : gaveta?.modo === 'editar'
              ? 'Edite os dados ou os responsáveis vinculados.'
              : 'O aluno precisa de ao menos um responsável com telefone ou e-mail.'
        }
        aoFechar={() => setGaveta(null)}
      >
        <FormAluno
          key={gaveta?.modo === 'editar' ? gaveta.aluno.id : 'novo'}
          aluno={gaveta?.modo === 'editar' ? gaveta.aluno : undefined}
          aoSalvar={aoSalvar}
          aoCancelar={() => setGaveta(null)}
        />
      </Gaveta>

      <Aviso mensagem={aviso} aoSumir={fecharAviso} />
    </>
  )
}

import { CalendarDays, ChevronLeft, ChevronRight, Plus } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { NOME_DA_BOLSA } from '../../api/cadastros'
import {
  listarMensalidades,
  NOME_DA_SITUACAO,
  type Mensalidade,
  type ResultadoDaGeracao,
  type SituacaoMensalidade,
} from '../../api/mensalidades'
import Aviso from '../../components/Aviso'
import Busca from '../../components/Busca'
import { Carregando, FalhaAoCarregar, Vazio } from '../../components/EstadoLista'
import Gaveta from '../../components/Gaveta'
import Monograma from '../../components/Monograma'
import { useAtraso } from '../../hooks/useAtraso'
import { useSessao } from '../../sessao/contexto'
import {
  formatarData,
  formatarMoeda,
  mesAtualIso,
  nomeDoMes,
  plural,
  somarMeses,
  somarValores,
} from '../../utils/formato'
import DetalheMensalidade from './DetalheMensalidade'
import GerarMensalidades from './GerarMensalidades'

type Filtro = 'todas' | SituacaoMensalidade

const FILTROS: { valor: Filtro; rotulo: string }[] = [
  { valor: 'todas', rotulo: 'Todas' },
  { valor: 'a_vencer', rotulo: 'A vencer' },
  { valor: 'atrasada', rotulo: 'Atrasadas' },
  { valor: 'paga', rotulo: 'Pagas' },
  { valor: 'isenta', rotulo: 'Isentas' },
  { valor: 'cancelada', rotulo: 'Canceladas' },
]

/** Texto do aviso depois de gerar, dizendo o que aconteceu e o que ficou de fora */
function mensagemDaGeracao(r: ResultadoDaGeracao): string {
  const partes: string[] = []
  if (r.geradas > 0) {
    partes.push(plural(r.geradas, 'mensalidade gerada', 'mensalidades geradas'))
  } else if (r.ja_existiam > 0) {
    partes.push('Todas as mensalidades deste mês já estavam geradas')
  } else {
    partes.push('Nenhuma mensalidade a gerar')
  }
  const detalhes: string[] = []
  if (r.geradas > 0 && r.ja_existiam > 0) detalhes.push(`${r.ja_existiam} já existiam`)
  if (r.bolsa_integral > 0) detalhes.push(`${r.bolsa_integral} com bolsa integral`)
  if (r.apadrinhados > 0) {
    detalhes.push(
      plural(
        r.apadrinhados,
        'apadrinhado, cobrado da empresa',
        'apadrinhados, cobrados da empresa',
      ),
    )
  }
  if (r.ainda_nao_comecaram > 0) detalhes.push(`${r.ainda_nao_comecaram} ainda não começaram`)
  return detalhes.length > 0 ? `${partes[0]} (${detalhes.join(', ')})` : partes[0]
}

function quando(m: Mensalidade): string {
  const vencimento = formatarData(m.data_vencimento)
  if (m.situacao === 'atrasada') {
    return `Venceu em ${vencimento} · ${plural(m.dias_em_atraso, 'dia', 'dias')} de atraso`
  }
  if (m.situacao === 'a_vencer') return `Vence em ${vencimento}`
  return `Vencimento em ${vencimento}`
}

function tituloDoPainel(m: Mensalidade | null): string {
  if (m?.status === 'paga') return 'Pagamento'
  if (m?.status === 'isenta') return 'Mensalidade isenta'
  if (m?.status === 'cancelada') return 'Mensalidade cancelada'
  return 'Mensalidade'
}

export default function Mensalidades() {
  const [mes, setMes] = useState(mesAtualIso)
  const [filtro, setFiltro] = useState<Filtro>('todas')
  const [busca, setBusca] = useState('')
  // Guarda de qual mês e busca é a lista. Se mudaram, ela não vale mais e a tela mostra "carregando"
  const [resposta, setResposta] = useState<{ chave: string; lista: Mensalidade[] } | null>(null)
  const [falhou, setFalhou] = useState(false)
  const [versao, setVersao] = useState(0)
  const [gerando, setGerando] = useState(false)
  // Mensalidade clicada, aberta no painel (pagamento, isenção ou dados do que já foi feito)
  const [clicada, setClicada] = useState<Mensalidade | null>(null)
  const [aviso, setAviso] = useState<string | null>(null)
  const buscaAtrasada = useAtraso(busca.trim())
  const { podeEditar } = useSessao()

  const chave = `${mes}|${buscaAtrasada}`
  const lista = resposta?.chave === chave ? resposta.lista : null

  // O mês seguinte ao atual é o último que a API deixa gerar
  const podeGerarEsteMes = mes <= somarMeses(mesAtualIso(), 1)

  useEffect(() => {
    const controle = new AbortController()
    listarMensalidades(mes, buscaAtrasada, controle.signal)
      .then((mensalidades) => {
        setResposta({ chave: `${mes}|${buscaAtrasada}`, lista: mensalidades })
        setFalhou(false)
      })
      .catch(() => {
        if (!controle.signal.aborted) setFalhou(true)
      })
    return () => controle.abort()
  }, [mes, buscaAtrasada, versao])

  function recarregar() {
    setFalhou(false)
    setVersao((v) => v + 1)
  }
  const fecharAviso = useCallback(() => setAviso(null), [])

  function aoGerar(resultado: ResultadoDaGeracao) {
    setGerando(false)
    setAviso(mensagemDaGeracao(resultado))
    recarregar()
  }

  function aoConcluir(mensagem: string) {
    setClicada(null)
    setAviso(mensagem)
    recarregar()
  }

  // Mostra a versão mais nova da lista (ex.: já paga por outra pessoa). Se a lista estiver
  // recarregando, mantém a que foi clicada, para o painel não sumir no meio do uso
  const aberta = (lista ?? []).find((m) => m.id === clicada?.id) ?? clicada

  const contagem = useMemo(() => {
    const total: Record<Filtro, number> = {
      todas: 0,
      a_vencer: 0,
      atrasada: 0,
      paga: 0,
      isenta: 0,
      cancelada: 0,
    }
    for (const m of lista ?? []) {
      total.todas += 1
      total[m.situacao] += 1
    }
    return total
  }, [lista])

  const totais = useMemo(() => {
    const valores = (...situacoes: SituacaoMensalidade[]) =>
      somarValores((lista ?? []).filter((m) => situacoes.includes(m.situacao)).map((m) => m.valor))
    return {
      cobrado: valores('a_vencer', 'atrasada', 'paga'),
      // O que entrou de verdade: pode ser diferente do valor da mensalidade
      pago: somarValores(
        (lista ?? []).flatMap((m) => (m.pagamento ? [m.pagamento.valor_pago] : [])),
      ),
      aVencer: valores('a_vencer'),
      atrasado: valores('atrasada'),
    }
  }, [lista])

  const visiveis = (lista ?? []).filter((m) => filtro === 'todas' || m.situacao === filtro)

  const botaoGerar = podeEditar && podeGerarEsteMes && (
    <button
      type="button"
      className="botao botao-principal botao-com-icone"
      onClick={() => setGerando(true)}
    >
      <Plus size={18} aria-hidden="true" />
      Gerar mensalidades
    </button>
  )

  return (
    <section className="pagina">
      <header className="pagina-cabecalho">
        <h1>Mensalidades</h1>
        <p>Veja quem está em dia, quem vence e quem está atrasado em cada mês.</p>
      </header>

      <div className="barra">
        <div className="seletor-mes" role="group" aria-label="Mês">
          <button type="button" aria-label="Mês anterior" onClick={() => setMes(somarMeses(mes, -1))}>
            <ChevronLeft size={18} aria-hidden="true" />
          </button>
          <output aria-live="polite">{nomeDoMes(mes)}</output>
          <button type="button" aria-label="Próximo mês" onClick={() => setMes(somarMeses(mes, 1))}>
            <ChevronRight size={18} aria-hidden="true" />
          </button>
        </div>
        {mes !== mesAtualIso() && (
          <button type="button" className="botao botao-texto" onClick={() => setMes(mesAtualIso())}>
            Mês atual
          </button>
        )}
        <Busca
          id="busca-mensalidades"
          rotulo="Buscar mensalidades"
          valor={busca}
          aoMudar={setBusca}
          placeholder="Buscar pelo nome do aluno"
        />
        {botaoGerar}
      </div>

      <div className="segmentos segmentos-largos" role="group" aria-label="Situação">
        {FILTROS.map((f) => (
          <button
            key={f.valor}
            type="button"
            aria-pressed={filtro === f.valor}
            onClick={() => setFiltro(f.valor)}
          >
            {f.rotulo}
            {lista !== null && <span className="contagem">{contagem[f.valor]}</span>}
          </button>
        ))}
      </div>

      {falhou ? (
        <FalhaAoCarregar oQue="as mensalidades" aoTentar={recarregar} />
      ) : lista === null ? (
        <Carregando />
      ) : lista.length === 0 ? (
        buscaAtrasada ? (
          <Vazio
            titulo={`Nenhuma mensalidade encontrada para “${buscaAtrasada}”`}
            texto="Confira a grafia do nome do aluno."
          />
        ) : (
          <Vazio
            titulo={`Nenhuma mensalidade em ${nomeDoMes(mes)}`}
            texto={
              podeEditar && podeGerarEsteMes
                ? 'Gere as mensalidades do mês para cobrar todas as matrículas ativas.'
                : 'As mensalidades deste mês ainda não foram geradas.'
            }
          >
            {botaoGerar}
          </Vazio>
        )
      ) : (
        <>
          <dl className="totais">
            <div>
              <dt>Cobrado no mês</dt>
              <dd>{formatarMoeda(totais.cobrado)}</dd>
            </div>
            <div>
              <dt>Já pago</dt>
              <dd>{formatarMoeda(totais.pago)}</dd>
            </div>
            <div>
              <dt>A vencer</dt>
              <dd>{formatarMoeda(totais.aVencer)}</dd>
            </div>
            <div className="totais-atraso">
              <dt>Em atraso</dt>
              <dd>{formatarMoeda(totais.atrasado)}</dd>
            </div>
          </dl>

          {visiveis.length === 0 ? (
            <Vazio
              titulo="Nenhuma mensalidade nesta situação"
              texto="Escolha outra situação para ver as demais mensalidades do mês."
            />
          ) : (
            <>
              <p className="resumo">
                {plural(visiveis.length, 'mensalidade', 'mensalidades')} em {nomeDoMes(mes)}
                {buscaAtrasada && ` para “${buscaAtrasada}”`}
              </p>
              <ul className="lista">
                {visiveis.map((m) => {
                  // Paga, isenta e cancelada: qualquer perfil vê os dados (e o motivo). Pendente: só quem
                  // pode editar abre, para registrar o pagamento (o administrador também isenta ou cancela)
                  const abre = m.status !== 'pendente' || podeEditar
                  const conteudo = (
                    <>
                      <Monograma nome={m.aluno.nome} apagado={!m.aluno.ativo} />
                      <span className="linha-principal">
                        <span className="linha-titulo">
                          {m.aluno.nome}
                          {m.bolsa !== 'nenhuma' && (
                            <span className="etiqueta etiqueta-bolsa">{NOME_DA_BOLSA[m.bolsa]}</span>
                          )}
                        </span>
                        <span className="linha-detalhes">
                          <span>
                            <CalendarDays size={14} aria-hidden="true" />
                            {quando(m)}
                          </span>
                        </span>
                      </span>
                      <span className="linha-lateral">
                        <span className="linha-rotulo">Valor</span>
                        <span>{formatarMoeda(m.valor)}</span>
                      </span>
                      <span className={`etiqueta etiqueta-${m.situacao}`}>
                        {NOME_DA_SITUACAO[m.situacao]}
                      </span>
                    </>
                  )
                  return (
                    <li key={m.id}>
                      {abre ? (
                        <button
                          type="button"
                          className="linha linha-parada linha-aberta"
                          onClick={() => setClicada(m)}
                        >
                          {conteudo}
                        </button>
                      ) : (
                        <div className="linha linha-parada">{conteudo}</div>
                      )}
                    </li>
                  )
                })}
              </ul>
            </>
          )}
        </>
      )}

      <Gaveta
        aberta={gerando}
        titulo="Gerar mensalidades"
        descricao="Cobra as matrículas em vigor no mês escolhido."
        aoFechar={() => setGerando(false)}
      >
        <GerarMensalidades mes={mes} aoGerar={aoGerar} aoCancelar={() => setGerando(false)} />
      </Gaveta>

      <Gaveta
        aberta={aberta !== null}
        titulo={tituloDoPainel(aberta)}
        descricao={
          aberta ? `${aberta.aluno.nome} · ${nomeDoMes(aberta.competencia.slice(0, 7))}` : ''
        }
        aoFechar={() => setClicada(null)}
      >
        {aberta && (
          <DetalheMensalidade
            key={aberta.id}
            mensalidade={aberta}
            aoConcluir={aoConcluir}
            aoDesatualizar={recarregar}
            aoFechar={() => setClicada(null)}
          />
        )}
      </Gaveta>

      <Aviso mensagem={aviso} aoSumir={fecharAviso} />
    </section>
  )
}

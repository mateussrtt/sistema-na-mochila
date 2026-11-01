import { CalendarDays, ChevronLeft, ChevronRight, FileText, Users } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'

import {
  listarCobrancas,
  NOME_DA_SITUACAO_COBRANCA,
  type Cobranca,
  type SituacaoCobranca,
} from '../../api/cobrancas'
import { listarPadrinhos, type Padrinho } from '../../api/padrinhos'
import Aviso from '../../components/Aviso'
import { Carregando, FalhaAoCarregar, Vazio } from '../../components/EstadoLista'
import Gaveta from '../../components/Gaveta'
import Monograma from '../../components/Monograma'
import {
  formatarData,
  formatarMoeda,
  mesAtualIso,
  nomeDoMes,
  nomeDoMesComMaiuscula,
  plural,
  somarMeses,
  somarValores,
} from '../../utils/formato'
import DetalheCobranca from './DetalheCobranca'

type Filtro = 'todas' | SituacaoCobranca

const FILTROS: { valor: Filtro; rotulo: string }[] = [
  { valor: 'todas', rotulo: 'Todas' },
  { valor: 'a_emitir', rotulo: 'A emitir' },
  { valor: 'a_vencer', rotulo: 'A vencer' },
  { valor: 'atrasada', rotulo: 'Atrasadas' },
  { valor: 'paga', rotulo: 'Pagas' },
  { valor: 'cancelada', rotulo: 'Canceladas' },
]

function quando(c: Cobranca): string {
  switch (c.situacao) {
    case 'a_emitir':
      return c.limite_emissao
        ? `Emitir a nota até ${formatarData(c.limite_emissao)}`
        : 'Nota ainda não emitida'
    case 'a_vencer':
      return `Vence em ${formatarData(c.data_vencimento)}`
    case 'atrasada':
      return `Venceu em ${formatarData(c.data_vencimento)} · ${plural(c.dias_em_atraso, 'dia', 'dias')} de atraso`
    case 'paga':
      return c.pagamento ? `Paga em ${formatarData(c.pagamento.data_pagamento)}` : 'Paga'
    case 'cancelada':
      return 'Cobrança cancelada'
  }
}

function tituloDoPainel(c: Cobranca | null): string {
  if (c?.status === 'paga') return 'Cobrança paga'
  if (c?.status === 'cancelada') return 'Cobrança cancelada'
  if (c?.status === 'emitida') return 'Nota emitida'
  return 'Nota a emitir'
}

export default function Cobrancas() {
  const [modo, setModo] = useState<'mes' | 'todos'>('mes')
  const [mes, setMes] = useState(mesAtualIso)
  const [filtro, setFiltro] = useState<Filtro>('todas')
  const [empresa, setEmpresa] = useState('')
  const [empresas, setEmpresas] = useState<Padrinho[]>([])
  // Guarda de qual mês e empresa é a lista. Se mudaram, ela não vale mais e a tela mostra "carregando"
  const [resposta, setResposta] = useState<{ chave: string; lista: Cobranca[] } | null>(null)
  const [falhou, setFalhou] = useState(false)
  const [versao, setVersao] = useState(0)
  const [clicada, setClicada] = useState<Cobranca | null>(null)
  const [aviso, setAviso] = useState<string | null>(null)

  const filtroDeMes = modo === 'mes' ? mes : ''
  const chave = `${filtroDeMes}|${empresa}`
  const lista = resposta?.chave === chave ? resposta.lista : null

  // As empresas do filtro: todas, inclusive as inativas, que ainda podem ter cobrança
  useEffect(() => {
    const controle = new AbortController()
    listarPadrinhos('', 'todos', controle.signal)
      .then(setEmpresas)
      .catch(() => {
        // Sem a lista de empresas o filtro some, mas a tela continua útil
      })
    return () => controle.abort()
  }, [])

  useEffect(() => {
    const controle = new AbortController()
    listarCobrancas(filtroDeMes, empresa ? Number(empresa) : null, controle.signal)
      .then((cobrancas) => {
        setResposta({ chave: `${filtroDeMes}|${empresa}`, lista: cobrancas })
        setFalhou(false)
      })
      .catch(() => {
        if (!controle.signal.aborted) setFalhou(true)
      })
    return () => controle.abort()
  }, [filtroDeMes, empresa, versao])

  function recarregar() {
    setFalhou(false)
    setVersao((v) => v + 1)
  }
  const fecharAviso = useCallback(() => setAviso(null), [])

  function aoConcluir(mensagem: string) {
    setClicada(null)
    setAviso(mensagem)
    recarregar()
  }

  // Mostra a versão mais nova da lista (ex.: já paga por outra pessoa). Se a lista estiver
  // recarregando, mantém a que foi clicada, para o painel não sumir no meio do uso
  const aberta = (lista ?? []).find((c) => c.id === clicada?.id) ?? clicada

  const contagem = useMemo(() => {
    const total: Record<Filtro, number> = {
      todas: 0,
      a_emitir: 0,
      a_vencer: 0,
      atrasada: 0,
      paga: 0,
      cancelada: 0,
    }
    for (const c of lista ?? []) {
      total.todas += 1
      total[c.situacao] += 1
    }
    return total
  }, [lista])

  const totais = useMemo(() => {
    const valores = (...situacoes: SituacaoCobranca[]) =>
      somarValores((lista ?? []).filter((c) => situacoes.includes(c.situacao)).map((c) => c.valor))
    return {
      aReceber: valores('a_emitir', 'a_vencer', 'atrasada'),
      aEmitir: valores('a_emitir'),
      // O que entrou de verdade: pode ser diferente do valor da cobrança
      recebido: somarValores(
        (lista ?? []).flatMap((c) => (c.pagamento ? [c.pagamento.valor_pago] : [])),
      ),
      atrasado: valores('atrasada'),
    }
  }, [lista])

  const foraDoPrazo = (lista ?? []).filter((c) => c.emissao_atrasada).length
  const visiveis = (lista ?? []).filter((c) => filtro === 'todas' || c.situacao === filtro)
  const periodo = modo === 'mes' ? `em ${nomeDoMes(mes)}` : 'em todos os meses'

  return (
    <section className="pagina">
      <header className="pagina-cabecalho">
        <h1>Cobrança de padrinhos</h1>
        <p>
          Quanto cada empresa padrinha deve no mês, a nota emitida e o pagamento. A cobrança nasce
          quando as mensalidades do mês são geradas.
        </p>
      </header>

      <div className="barra">
        <div className="segmentos" role="group" aria-label="Período">
          <button type="button" aria-pressed={modo === 'mes'} onClick={() => setModo('mes')}>
            Um mês
          </button>
          <button type="button" aria-pressed={modo === 'todos'} onClick={() => setModo('todos')}>
            Todos os meses
          </button>
        </div>
        {modo === 'mes' && (
          <div className="seletor-mes" role="group" aria-label="Mês">
            <button type="button" aria-label="Mês anterior" onClick={() => setMes(somarMeses(mes, -1))}>
              <ChevronLeft size={18} aria-hidden="true" />
            </button>
            <output aria-live="polite">{nomeDoMes(mes)}</output>
            <button type="button" aria-label="Próximo mês" onClick={() => setMes(somarMeses(mes, 1))}>
              <ChevronRight size={18} aria-hidden="true" />
            </button>
          </div>
        )}
        {modo === 'mes' && mes !== mesAtualIso() && (
          <button type="button" className="botao botao-texto" onClick={() => setMes(mesAtualIso())}>
            Mês atual
          </button>
        )}
        {empresas.length > 0 && (
          <select
            className="filtro-select"
            aria-label="Empresa padrinha"
            value={empresa}
            onChange={(e) => setEmpresa(e.target.value)}
          >
            <option value="">Todas as empresas</option>
            {empresas.map((p) => (
              <option key={p.id} value={p.id}>
                {p.nome}
                {!p.ativo && ' (inativa)'}
              </option>
            ))}
          </select>
        )}
      </div>

      {lista !== null && contagem.a_emitir > 0 && (
        <button
          type="button"
          className={`destaque-emitir${foraDoPrazo > 0 ? ' destaque-emitir-atraso' : ''}`}
          onClick={() => setFiltro('a_emitir')}
        >
          <FileText size={20} aria-hidden="true" />
          <span>
            <strong>
              {plural(contagem.a_emitir, 'nota a emitir', 'notas a emitir')} ·{' '}
              {formatarMoeda(totais.aEmitir)}
            </strong>
            {foraDoPrazo > 0 && (
              <span>
                {' '}
                — {plural(foraDoPrazo, 'já passou', 'já passaram')} do prazo combinado com a empresa
              </span>
            )}
          </span>
        </button>
      )}

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
        <FalhaAoCarregar oQue="as cobranças" aoTentar={recarregar} />
      ) : lista === null ? (
        <Carregando />
      ) : lista.length === 0 ? (
        <Vazio
          titulo={`Nenhuma cobrança ${periodo}`}
          texto="As cobranças aparecem quando as mensalidades do mês são geradas e há alunos apadrinhados por empresas."
        />
      ) : (
        <>
          <dl className="totais">
            <div>
              <dt>A receber</dt>
              <dd>{formatarMoeda(totais.aReceber)}</dd>
            </div>
            <div>
              <dt>Notas a emitir</dt>
              <dd>{formatarMoeda(totais.aEmitir)}</dd>
            </div>
            <div>
              <dt>Já recebido</dt>
              <dd>{formatarMoeda(totais.recebido)}</dd>
            </div>
            <div className="totais-atraso">
              <dt>Em atraso</dt>
              <dd>{formatarMoeda(totais.atrasado)}</dd>
            </div>
          </dl>

          {visiveis.length === 0 ? (
            <Vazio
              titulo="Nenhuma cobrança nesta situação"
              texto="Escolha outra situação para ver as demais cobranças."
            />
          ) : (
            <>
              <p className="resumo">
                {plural(visiveis.length, 'cobrança', 'cobranças')} {periodo}
              </p>
              <ul className="lista">
                {visiveis.map((c) => (
                  <li key={c.id}>
                    <button
                      type="button"
                      className="linha linha-parada linha-aberta"
                      onClick={() => setClicada(c)}
                    >
                      <Monograma nome={c.padrinho.nome} apagado={!c.padrinho.ativo} />
                      <span className="linha-principal">
                        <span className="linha-titulo">
                          {c.padrinho.nome}
                          {c.emissao_atrasada && (
                            <span className="etiqueta etiqueta-atrasada">Emissão atrasada</span>
                          )}
                        </span>
                        <span className="linha-detalhes">
                          {modo === 'todos' && (
                            <span>
                              <CalendarDays size={14} aria-hidden="true" />
                              {nomeDoMesComMaiuscula(c.competencia.slice(0, 7))}
                            </span>
                          )}
                          <span>
                            <Users size={14} aria-hidden="true" />
                            {plural(c.alunos.length, 'aluno', 'alunos')}
                          </span>
                          <span>{quando(c)}</span>
                        </span>
                      </span>
                      <span className="linha-lateral">
                        <span className="linha-rotulo">Valor</span>
                        <span>{formatarMoeda(c.valor)}</span>
                      </span>
                      <span className={`etiqueta etiqueta-${c.situacao}`}>
                        {NOME_DA_SITUACAO_COBRANCA[c.situacao]}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </>
      )}

      <Gaveta
        aberta={aberta !== null}
        titulo={tituloDoPainel(aberta)}
        descricao={
          aberta
            ? `${aberta.padrinho.nome} · ${nomeDoMes(aberta.competencia.slice(0, 7))}`
            : ''
        }
        aoFechar={() => setClicada(null)}
      >
        {aberta && (
          <DetalheCobranca
            key={aberta.id}
            cobranca={aberta}
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

import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router'

import { consultarPeriodo, type PeriodoDoCaixa } from '../../api/caixa'
import { ApiError } from '../../api/client'
import { Carregando, FalhaAoCarregar } from '../../components/EstadoLista'
import {
  formatarMoeda,
  mesAtualIso,
  nomeDoMes,
  nomeDoMesComMaiuscula,
  plural,
  somarMeses,
} from '../../utils/formato'
import {
  ATALHOS,
  erroDoPeriodo,
  mesValido,
  periodoDoAtalho,
  periodoDoEndereco,
  rotuloDoPeriodo,
} from '../../utils/periodo'
import ListaDoFluxo from './ListaDoFluxo'
import MesesDoPeriodo from './MesesDoPeriodo'

function lancamentos(quantidade: number): string {
  return plural(quantidade, 'lançamento', 'lançamentos')
}

/** Escolhe um mês com as setas, como nas outras telas. Não deixa passar do mês atual. */
function SeletorDeMes(props: {
  rotulo: string
  mes: string
  atual: string
  aoMudar: (mes: string) => void
}) {
  const { rotulo, mes, atual, aoMudar } = props
  return (
    <div className="periodo-campo">
      <span className="periodo-rotulo" id={`periodo-${rotulo}`}>
        {rotulo}
      </span>
      <div className="seletor-mes" role="group" aria-labelledby={`periodo-${rotulo}`}>
        <button type="button" aria-label={`${rotulo}: mês anterior`} onClick={() => aoMudar(somarMeses(mes, -1))}>
          <ChevronLeft size={18} aria-hidden="true" />
        </button>
        <output aria-live="polite">{nomeDoMes(mes)}</output>
        <button
          type="button"
          aria-label={`${rotulo}: próximo mês`}
          disabled={mes >= atual}
          onClick={() => aoMudar(somarMeses(mes, 1))}
        >
          <ChevronRight size={18} aria-hidden="true" />
        </button>
      </div>
    </div>
  )
}

export default function Caixa() {
  const atual = mesAtualIso()
  // O período fica no endereço (/caixa?de=2026-09&ate=2026-11): recarregar não perde o filtro
  const [parametros, setParametros] = useSearchParams()
  const { de, ate } = periodoDoEndereco(parametros.get('de'), parametros.get('ate'), atual)
  const erroDaTela = erroDoPeriodo(de, ate, atual)
  // Guarda de qual período é o resultado. Se o período mudou, ele não vale mais
  const chave = `${de}|${ate}`
  const [resposta, setResposta] = useState<{ chave: string; periodo: PeriodoDoCaixa } | null>(null)
  const [erroDaApi, setErroDaApi] = useState<string | null>(null)
  const [falhou, setFalhou] = useState(false)
  const [versao, setVersao] = useState(0)

  const periodo = resposta?.chave === chave ? resposta.periodo : null
  const erro = erroDaTela ?? erroDaApi

  useEffect(() => {
    if (erroDaTela) return
    const controle = new AbortController()
    consultarPeriodo(de, ate, controle.signal)
      .then((dados) => {
        setResposta({ chave: `${de}|${ate}`, periodo: dados })
        setErroDaApi(null)
        setFalhou(false)
      })
      .catch((falha) => {
        if (controle.signal.aborted) return
        // Um período que a API recusa (422) vira a mensagem dela; o resto é falha de conexão
        if (falha instanceof ApiError && falha.status === 422) {
          setErroDaApi(falha.message)
          setFalhou(false)
        } else {
          setFalhou(true)
        }
      })
    return () => controle.abort()
  }, [de, ate, erroDaTela, versao])

  function escolher(novoDe: string, novoAte: string, trocarHistorico = false) {
    setErroDaApi(null)
    setParametros({ de: novoDe, ate: novoAte }, { replace: trocarHistorico })
  }

  function recarregar() {
    setFalhou(false)
    setVersao((v) => v + 1)
  }

  // Os seletores mostram um mês de verdade mesmo que o endereço tenha um valor torto
  const deNoSeletor = mesValido(de) ? de : atual
  const ateNoSeletor = mesValido(ate) ? ate : atual
  const umMes = de === ate
  const rotulo = rotuloDoPeriodo(de, ate)
  const saldo = periodo ? Number(periodo.total.saldo) : 0
  const semMovimento =
    periodo !== null && periodo.total.entradas.quantidade + periodo.total.saidas.quantidade === 0

  return (
    <section className="pagina">
      <header className="pagina-cabecalho">
        <h1>Caixa</h1>
        <p>
          O saldo e o fluxo de caixa de um mês ou de um período de até 12 meses: o que entrou e o
          que saiu, por categoria, contando o dia em que o dinheiro realmente entrou ou saiu.
        </p>
      </header>

      <div className="barra">
        <div className="segmentos" role="group" aria-label="Atalhos de período">
          {ATALHOS.map((atalho) => {
            const alvo = periodoDoAtalho(atalho.id, atual)
            return (
              <button
                key={atalho.id}
                type="button"
                aria-pressed={de === alvo.de && ate === alvo.ate}
                onClick={() => escolher(alvo.de, alvo.ate)}
              >
                {atalho.rotulo}
              </button>
            )
          })}
        </div>
      </div>

      <div className="barra periodo-barra">
        <SeletorDeMes
          rotulo="De"
          mes={deNoSeletor}
          atual={atual}
          aoMudar={(mes) => escolher(mes, ate, true)}
        />
        <SeletorDeMes
          rotulo="Até"
          mes={ateNoSeletor}
          atual={atual}
          aoMudar={(mes) => escolher(de, mes, true)}
        />
      </div>

      {erro ? (
        <p className="erro-geral" role="alert">
          {erro}
        </p>
      ) : falhou ? (
        <FalhaAoCarregar oQue="o caixa" aoTentar={recarregar} />
      ) : periodo === null ? (
        <Carregando linhas={2} />
      ) : (
        <>
          <dl className="totais totais-tres">
            <div>
              <dt>Entradas</dt>
              <dd>{formatarMoeda(periodo.total.entradas.total)}</dd>
              <dd className="totais-detalhe">{lancamentos(periodo.total.entradas.quantidade)}</dd>
            </div>
            <div>
              <dt>Saídas</dt>
              <dd>{formatarMoeda(periodo.total.saidas.total)}</dd>
              <dd className="totais-detalhe">{lancamentos(periodo.total.saidas.quantidade)}</dd>
            </div>
            <div className={saldo < 0 ? 'saldo-negativo' : 'saldo-positivo'}>
              <dt>{umMes ? `Saldo de ${nomeDoMesComMaiuscula(de)}` : 'Saldo do período'}</dt>
              <dd>{formatarMoeda(periodo.total.saldo)}</dd>
              <dd className="totais-detalhe">
                {saldo < 0 ? 'Saiu mais do que entrou' : saldo > 0 ? 'Fechou no azul' : 'Sem diferença'}
              </dd>
            </div>
          </dl>

          {!umMes && (
            <p className="resumo">
              Total de {rotulo} · {plural(periodo.quantidade_de_meses, 'mês', 'meses')}
            </p>
          )}

          {semMovimento && <p className="resumo">Nenhum dinheiro entrou nem saiu em {rotulo}.</p>}

          {!umMes && (
            <MesesDoPeriodo
              meses={periodo.meses}
              aoEscolher={(mes) => escolher(mes, mes)}
            />
          )}

          <div className="fluxo">
            <ListaDoFluxo
              titulo="De onde entrou o dinheiro"
              lado="entradas"
              linhas={periodo.total.entradas_por_categoria}
              total={periodo.total.entradas.total}
              vazio={`Nada entrou em ${rotulo}.`}
            />
            <ListaDoFluxo
              titulo="Para onde foi o dinheiro"
              lado="saidas"
              linhas={periodo.total.saidas_por_categoria}
              total={periodo.total.saidas.total}
              vazio={`Nada saiu em ${rotulo}.`}
            />
          </div>

          <p className="nota nota-caixa">
            Entra no mês o pagamento recebido nele, mesmo de uma mensalidade de outro mês. Os
            lançamentos cancelados não são contados.
          </p>
        </>
      )}
    </section>
  )
}

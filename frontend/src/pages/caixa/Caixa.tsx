import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useEffect, useState } from 'react'

import { consultarCaixa, type Caixa as CaixaDoMes } from '../../api/caixa'
import { Carregando, FalhaAoCarregar } from '../../components/EstadoLista'
import {
  formatarMoeda,
  mesAtualIso,
  nomeDoMes,
  nomeDoMesComMaiuscula,
  plural,
  somarMeses,
} from '../../utils/formato'

function lancamentos(quantidade: number): string {
  return plural(quantidade, 'lançamento', 'lançamentos')
}

export default function Caixa() {
  const [mes, setMes] = useState(mesAtualIso)
  // Guarda de qual mês é o resultado. Se o mês mudou, ele não vale mais e a tela mostra "carregando"
  const [resposta, setResposta] = useState<{ mes: string; caixa: CaixaDoMes } | null>(null)
  const [falhou, setFalhou] = useState(false)
  const [versao, setVersao] = useState(0)

  const caixa = resposta?.mes === mes ? resposta.caixa : null
  // Nenhum lançamento tem data no futuro: o caixa só existe até o mês atual
  const noMesAtual = mes >= mesAtualIso()

  useEffect(() => {
    const controle = new AbortController()
    consultarCaixa(mes, controle.signal)
      .then((dados) => {
        setResposta({ mes, caixa: dados })
        setFalhou(false)
      })
      .catch(() => {
        if (!controle.signal.aborted) setFalhou(true)
      })
    return () => controle.abort()
  }, [mes, versao])

  function recarregar() {
    setFalhou(false)
    setVersao((v) => v + 1)
  }

  const saldo = caixa ? Number(caixa.saldo) : 0
  const semMovimento = caixa !== null && caixa.entradas.quantidade + caixa.saidas.quantidade === 0

  return (
    <section className="pagina">
      <header className="pagina-cabecalho">
        <h1>Caixa</h1>
        <p>
          O saldo do mês: o que entrou menos o que saiu, contando o dia em que o dinheiro
          realmente entrou ou saiu.
        </p>
      </header>

      <div className="barra">
        <div className="seletor-mes" role="group" aria-label="Mês">
          <button type="button" aria-label="Mês anterior" onClick={() => setMes(somarMeses(mes, -1))}>
            <ChevronLeft size={18} aria-hidden="true" />
          </button>
          <output aria-live="polite">{nomeDoMes(mes)}</output>
          <button
            type="button"
            aria-label="Próximo mês"
            disabled={noMesAtual}
            onClick={() => setMes(somarMeses(mes, 1))}
          >
            <ChevronRight size={18} aria-hidden="true" />
          </button>
        </div>
        {mes !== mesAtualIso() && (
          <button type="button" className="botao botao-texto" onClick={() => setMes(mesAtualIso())}>
            Mês atual
          </button>
        )}
      </div>

      {falhou ? (
        <FalhaAoCarregar oQue="o caixa" aoTentar={recarregar} />
      ) : caixa === null ? (
        <Carregando linhas={2} />
      ) : (
        <>
          <dl className="totais totais-tres">
            <div>
              <dt>Entradas</dt>
              <dd>{formatarMoeda(caixa.entradas.total)}</dd>
              <dd className="totais-detalhe">{lancamentos(caixa.entradas.quantidade)}</dd>
            </div>
            <div>
              <dt>Saídas</dt>
              <dd>{formatarMoeda(caixa.saidas.total)}</dd>
              <dd className="totais-detalhe">{lancamentos(caixa.saidas.quantidade)}</dd>
            </div>
            <div className={saldo < 0 ? 'saldo-negativo' : 'saldo-positivo'}>
              <dt>Saldo de {nomeDoMesComMaiuscula(mes)}</dt>
              <dd>{formatarMoeda(caixa.saldo)}</dd>
              <dd className="totais-detalhe">
                {saldo < 0 ? 'Saiu mais do que entrou' : saldo > 0 ? 'Fechou no azul' : 'Sem diferença'}
              </dd>
            </div>
          </dl>

          {semMovimento && (
            <p className="resumo">Nenhum dinheiro entrou nem saiu em {nomeDoMes(mes)}.</p>
          )}

          <section className="por-categoria" aria-label="Entradas por origem">
            <h2>De onde entrou o dinheiro</h2>
            <ul>
              {caixa.origens_das_entradas.map((origem) => (
                <li key={origem.origem}>
                  <span className="origem-nome">
                    {origem.rotulo}
                    <span className="mais">{lancamentos(origem.quantidade)}</span>
                  </span>
                  <strong>{formatarMoeda(origem.total)}</strong>
                </li>
              ))}
            </ul>
          </section>

          <p className="nota nota-caixa">
            Entra no mês o pagamento recebido nele, mesmo de uma mensalidade de outro mês. Os
            lançamentos cancelados não são contados.
          </p>
        </>
      )}
    </section>
  )
}

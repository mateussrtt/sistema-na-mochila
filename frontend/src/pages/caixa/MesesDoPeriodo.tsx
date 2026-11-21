import type { MesDoPeriodo } from '../../api/caixa'
import { formatarMoeda, nomeDoMesComMaiuscula, plural } from '../../utils/formato'

type Props = {
  meses: MesDoPeriodo[]
  /** Clicar num mês abre só o caixa dele */
  aoEscolher: (mes: string) => void
}

/** Cada mês do período, lado a lado, com entradas, saídas e saldo (RF24) */
export default function MesesDoPeriodo({ meses, aoEscolher }: Props) {
  return (
    <section className="meses-do-periodo" aria-labelledby="meses-do-periodo-titulo">
      <h2 id="meses-do-periodo-titulo">Mês a mês</h2>
      <ul>
        {meses.map((mes) => {
          const saldo = Number(mes.saldo)
          const movimentos = mes.entradas.quantidade + mes.saidas.quantidade
          return (
            <li key={mes.mes}>
              <button
                type="button"
                className="mes-do-periodo"
                onClick={() => aoEscolher(mes.mes)}
                aria-label={`Ver só ${nomeDoMesComMaiuscula(mes.mes)}`}
              >
                <span className="mes-nome">
                  {nomeDoMesComMaiuscula(mes.mes)}
                  <span className="mais">{plural(movimentos, 'lançamento', 'lançamentos')}</span>
                </span>
                <span className="mes-valor">
                  <span className="mes-rotulo">Entradas</span>
                  {formatarMoeda(mes.entradas.total)}
                </span>
                <span className="mes-valor">
                  <span className="mes-rotulo">Saídas</span>
                  {formatarMoeda(mes.saidas.total)}
                </span>
                <span className={`mes-valor mes-saldo ${saldo < 0 ? 'saldo-negativo' : 'saldo-positivo'}`}>
                  <span className="mes-rotulo">Saldo</span>
                  {formatarMoeda(mes.saldo)}
                </span>
              </button>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

import type { Cancelamento } from '../api/cancelamento'
import { formatarData, formatarDataHora, formatarMoeda } from '../utils/formato'

type PagamentoCancelado = {
  data_pagamento: string
  valor_pago: string
  forma_pagamento: string
  registrado_por: string
  cancelamento: Cancelamento
}

type Props = {
  pagamentos: PagamentoCancelado[]
  /** Nome de cada forma de pagamento. Ex.: { pix: 'PIX' } */
  nomeDaForma: Record<string, string>
}

/** Histórico dos pagamentos registrados errado e cancelados (RF17, RN12) */
export default function PagamentosCancelados({ pagamentos, nomeDaForma }: Props) {
  if (pagamentos.length === 0) return null
  return (
    <fieldset className="grupo">
      <legend>{pagamentos.length === 1 ? 'Pagamento cancelado' : 'Pagamentos cancelados'}</legend>
      <ul className="cancelados">
        {pagamentos.map((p) => (
          <li key={p.cancelamento.cancelado_em}>
            <span className="cancelados-valor">
              {formatarMoeda(p.valor_pago)} em {formatarData(p.data_pagamento)} (
              {nomeDaForma[p.forma_pagamento] ?? p.forma_pagamento}), registrado por{' '}
              {p.registrado_por}
            </span>
            <span>
              Cancelado por {p.cancelamento.cancelado_por}, em{' '}
              {formatarDataHora(p.cancelamento.cancelado_em)}: {p.cancelamento.motivo}
            </span>
          </li>
        ))}
      </ul>
    </fieldset>
  )
}

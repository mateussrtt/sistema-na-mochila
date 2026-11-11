import type { Cancelamento } from '../api/cancelamento'
import { formatarDataHora } from '../utils/formato'

type Props = {
  cancelamento: Cancelamento
}

/** Motivo, quem cancelou e quando, na tela de detalhes do lançamento (RF26) */
export default function CancelamentoDoLancamento({ cancelamento }: Props) {
  return (
    <fieldset className="grupo">
      <legend>Cancelamento</legend>
      <dl className="dados">
        <dt>Motivo</dt>
        <dd>{cancelamento.motivo}</dd>
        <dt>Cancelado por</dt>
        <dd>
          {cancelamento.cancelado_por}, em {formatarDataHora(cancelamento.cancelado_em)}
        </dd>
      </dl>
    </fieldset>
  )
}

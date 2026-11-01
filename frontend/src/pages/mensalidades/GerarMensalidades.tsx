import { useState, type FormEvent } from 'react'

import { ApiError } from '../../api/client'
import { gerarMensalidades, type ResultadoDaGeracao } from '../../api/mensalidades'
import { nomeDoMes } from '../../utils/formato'

type Props = {
  /** Mês que está aberto na tela, no formato AAAA-MM */
  mes: string
  aoGerar: (resultado: ResultadoDaGeracao) => void
  aoCancelar: () => void
}

/** Pede a confirmação antes de gerar: uma mensalidade gerada por engano só se desfaz cancelando. */
export default function GerarMensalidades({ mes, aoGerar, aoCancelar }: Props) {
  const [gerando, setGerando] = useState(false)
  const [erro, setErro] = useState<string | undefined>()

  async function aoEnviar(evento: FormEvent) {
    evento.preventDefault()
    setGerando(true)
    setErro(undefined)
    try {
      aoGerar(await gerarMensalidades(mes))
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : 'Não foi possível gerar. Tente de novo.')
    } finally {
      setGerando(false)
    }
  }

  return (
    <form className="gaveta-formulario" noValidate onSubmit={(e) => void aoEnviar(e)}>
      <div className="gaveta-conteudo">
        <p>
          Serão geradas as mensalidades de <strong>{nomeDoMes(mes)}</strong>.
        </p>
        <ul className="regras">
          <li>
            Uma mensalidade para cada matrícula em vigor no mês, com o valor da matrícula. Quem
            saiu durante o mês também é cobrado nele.
          </li>
          <li>
            O vencimento é no dia 10. Para quem entrou depois do dia 10, vence na data de início.
          </li>
          <li>Se o aluno saiu e voltou no mesmo mês, vale a matrícula mais recente.</li>
          <li>Quem tem bolsa integral não paga e fica de fora.</li>
          <li>
            Quem é apadrinhado por uma empresa também fica de fora: a empresa é quem paga, e não o
            responsável.
          </li>
          <li>Matrículas que só começam depois deste mês ficam de fora.</li>
          <li>
            Pode gerar de novo sem medo: o que já existe não é repetido, só entra o que estiver
            faltando.
          </li>
        </ul>
        {erro && (
          <p className="erro-geral" role="alert">
            {erro}
          </p>
        )}
      </div>

      <footer className="gaveta-rodape">
        <span />
        <div className="gaveta-rodape-acoes">
          <button type="button" className="botao botao-texto" onClick={aoCancelar}>
            Cancelar
          </button>
          <button type="submit" className="botao botao-principal" disabled={gerando}>
            {gerando ? 'Gerando…' : 'Gerar mensalidades'}
          </button>
        </div>
      </footer>
    </form>
  )
}

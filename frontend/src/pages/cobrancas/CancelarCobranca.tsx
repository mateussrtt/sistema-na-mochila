import { useState, type FormEvent } from 'react'

import { ApiError } from '../../api/client'
import { cancelarCobranca, type Cobranca } from '../../api/cobrancas'
import Campo from '../../components/Campo'
import { ligacaoDoCampo } from '../../utils/campo'
import { formatarMoeda, nomeDoMesComMaiuscula, plural } from '../../utils/formato'

const MOTIVO_MINIMO = 3
const MOTIVO_MAXIMO = 255
const DICA =
  'Escreva só o necessário: o motivo fica registrado com o seu nome e pode ser visto por quem usa o sistema.'

type Props = {
  cobranca: Cobranca
  aoCancelar: (mensagem: string) => void
  aoDesatualizar: () => void
  aoVoltar: () => void
}

/** Cancela a cobrança inteira, só para o administrador (RN12, RN13). */
export default function CancelarCobranca({ cobranca, aoCancelar, aoDesatualizar, aoVoltar }: Props) {
  const [motivo, setMotivo] = useState('')
  const [tentou, setTentou] = useState(false)
  const [salvando, setSalvando] = useState(false)
  const [erroApi, setErroApi] = useState<{ motivo?: string; geral?: string }>({})

  function erroDoMotivo(): string | undefined {
    const limpo = motivo.trim()
    if (!limpo) return 'Informe o motivo.'
    if (limpo.length < MOTIVO_MINIMO) {
      return `Explique o motivo com pelo menos ${MOTIVO_MINIMO} letras.`
    }
    if (limpo.length > MOTIVO_MAXIMO) return `Use no máximo ${MOTIVO_MAXIMO} caracteres.`
  }

  const erroMotivo = (tentou ? erroDoMotivo() : undefined) ?? erroApi.motivo

  async function aoEnviar(evento: FormEvent) {
    evento.preventDefault()
    setTentou(true)
    setErroApi({})
    if (erroDoMotivo()) return

    setSalvando(true)
    try {
      await cancelarCobranca(cobranca.id, motivo.trim())
      aoCancelar(`Cobrança de ${cobranca.padrinho.nome} cancelada`)
    } catch (erro) {
      if (erro instanceof ApiError && erro.campos.motivo) {
        setErroApi({ motivo: erro.campos.motivo })
        return
      }
      if (erro instanceof ApiError && erro.status === 409) aoDesatualizar()
      setErroApi({
        geral: erro instanceof ApiError ? erro.message : 'Não foi possível cancelar. Tente de novo.',
      })
    } finally {
      setSalvando(false)
    }
  }

  return (
    <form className="gaveta-formulario" noValidate onSubmit={(e) => void aoEnviar(e)}>
      <div className="gaveta-conteudo">
        <dl className="dados">
          <dt>Empresa</dt>
          <dd>{cobranca.padrinho.nome}</dd>
          <dt>Mês</dt>
          <dd>{nomeDoMesComMaiuscula(cobranca.competencia.slice(0, 7))}</dd>
          <dt>Valor</dt>
          <dd>{formatarMoeda(cobranca.valor)}</dd>
          <dt>Alunos</dt>
          <dd>{plural(cobranca.alunos.length, 'aluno', 'alunos')}</dd>
        </dl>

        <fieldset className="grupo">
          <legend>Cancelar a cobrança</legend>
          <p className="campo-dica">
            Use quando a cobrança foi gerada por engano ou a empresa deixou de pagar. As
            mensalidades dos alunos também são canceladas. Nada é apagado: tudo continua no
            histórico, com o motivo.
          </p>
          <Campo id="cancelar-motivo" rotulo="Motivo" erro={erroMotivo} dica={DICA}>
            <input
              {...ligacaoDoCampo('cancelar-motivo', erroMotivo, DICA)}
              autoComplete="off"
              maxLength={MOTIVO_MAXIMO}
              value={motivo}
              onChange={(e) => setMotivo(e.target.value)}
            />
          </Campo>
          {cobranca.nota && (
            <p className="aviso-valor" role="note">
              A nota {cobranca.nota.numero_nota} já foi registrada. Se ela foi emitida, cancele-a
              também fora do sistema.
            </p>
          )}
          <p className="aviso-valor" role="note">
            Isto não pode ser desfeito pela tela, e as mensalidades deste mês não são geradas de
            novo.
          </p>
        </fieldset>

        {erroApi.geral && (
          <p className="erro-geral" role="alert">
            {erroApi.geral}
          </p>
        )}
      </div>

      <footer className="gaveta-rodape">
        <span />
        <div className="gaveta-rodape-acoes">
          <button type="button" className="botao botao-texto" onClick={aoVoltar}>
            Voltar
          </button>
          <button type="submit" className="botao botao-perigo" disabled={salvando}>
            {salvando ? 'Cancelando…' : 'Cancelar cobrança'}
          </button>
        </div>
      </footer>
    </form>
  )
}

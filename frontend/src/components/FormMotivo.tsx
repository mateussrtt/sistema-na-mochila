import { useState, type FormEvent, type ReactNode } from 'react'

import { ApiError } from '../api/client'
import { ligacaoDoCampo } from '../utils/campo'
import { DICA_DO_MOTIVO, MOTIVO_MAXIMO, erroDoMotivo } from '../utils/motivo'
import Campo from './Campo'

type Props = {
  id: string
  /** O que está sendo cancelado, para conferir antes de confirmar */
  resumo: ReactNode
  legenda: string
  explicacao: ReactNode
  botao: string
  /** Texto do botão enquanto envia. Ex.: "Cancelando…" */
  fazendo: string
  /** Envia o motivo para a API. Se der certo, quem chamou mostra a confirmação. */
  enviar: (motivo: string) => Promise<void>
  /** A API disse que o lançamento mudou (ex.: outra pessoa já cancelou): recarrega a lista */
  aoDesatualizar: () => void
  aoVoltar: () => void
}

/**
 * Confirma um cancelamento pedindo o motivo, só para o administrador (RF17, RN13).
 * Fica numa tela à parte: apertar Enter em outro formulário nunca cancela nada.
 */
export default function FormMotivo({
  id,
  resumo,
  legenda,
  explicacao,
  botao,
  fazendo,
  enviar,
  aoDesatualizar,
  aoVoltar,
}: Props) {
  const [motivo, setMotivo] = useState('')
  const [tentou, setTentou] = useState(false)
  const [salvando, setSalvando] = useState(false)
  const [erroApi, setErroApi] = useState<{ motivo?: string; geral?: string }>({})

  const erroMotivo = (tentou ? erroDoMotivo(motivo) : undefined) ?? erroApi.motivo
  const campo = `${id}-motivo`

  async function aoEnviar(evento: FormEvent) {
    evento.preventDefault()
    setTentou(true)
    setErroApi({})
    if (erroDoMotivo(motivo)) return

    setSalvando(true)
    try {
      await enviar(motivo.trim())
    } catch (erro) {
      if (erro instanceof ApiError && erro.campos.motivo) {
        setErroApi({ motivo: erro.campos.motivo })
        return
      }
      if (erro instanceof ApiError && erro.status === 409) aoDesatualizar()
      setErroApi({
        geral:
          erro instanceof ApiError ? erro.message : 'Não foi possível cancelar. Tente de novo.',
      })
    } finally {
      setSalvando(false)
    }
  }

  return (
    <form className="gaveta-formulario" noValidate onSubmit={(e) => void aoEnviar(e)}>
      <div className="gaveta-conteudo">
        {resumo}

        <fieldset className="grupo">
          <legend>{legenda}</legend>
          <p className="campo-dica">{explicacao}</p>
          <Campo id={campo} rotulo="Motivo" erro={erroMotivo} dica={DICA_DO_MOTIVO}>
            <input
              {...ligacaoDoCampo(campo, erroMotivo, DICA_DO_MOTIVO)}
              autoComplete="off"
              maxLength={MOTIVO_MAXIMO}
              value={motivo}
              onChange={(e) => setMotivo(e.target.value)}
            />
          </Campo>
          <p className="aviso-valor" role="note">
            Isto não pode ser desfeito pela tela. Nada é apagado: o lançamento cancelado continua no
            histórico, com o motivo, o seu nome e a hora.
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
            {salvando ? fazendo : botao}
          </button>
        </div>
      </footer>
    </form>
  )
}

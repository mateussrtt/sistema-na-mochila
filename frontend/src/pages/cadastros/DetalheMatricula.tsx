import { useState, type FormEvent } from 'react'

import { encerrarMatricula, type Matricula } from '../../api/cadastros'
import { ApiError } from '../../api/client'
import Campo from '../../components/Campo'
import { useSessao } from '../../sessao/contexto'
import { ligacaoDoCampo } from '../../utils/campo'
import { formatarData, formatarMoeda, hojeIso } from '../../utils/formato'

type Props = {
  matricula: Matricula
  aoEncerrar: (mensagem: string) => void
  aoFechar: () => void
}

/** Dados da matrícula. Se ainda estiver ativa, permite encerrar. */
export default function DetalheMatricula({ matricula, aoEncerrar, aoFechar }: Props) {
  const [data, setData] = useState(hojeIso())
  const [erro, setErro] = useState<string | undefined>()
  const [salvando, setSalvando] = useState(false)
  const { podeEditar } = useSessao()
  const ativa = matricula.situacao === 'ativa'
  // O perfil de consulta vê os dados, mas não encerra
  const encerravel = ativa && podeEditar

  async function aoEnviar(evento: FormEvent) {
    evento.preventDefault()
    if (!data) {
      setErro('Informe a data de encerramento.')
      return
    }
    if (data < matricula.data_inicio) {
      setErro('A data de encerramento não pode ser antes do início da matrícula.')
      return
    }
    if (data > hojeIso()) {
      setErro('A data de encerramento não pode ser no futuro.')
      return
    }

    setSalvando(true)
    setErro(undefined)
    try {
      await encerrarMatricula(matricula.id, data)
      aoEncerrar('Matrícula encerrada')
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : 'Não foi possível encerrar. Tente de novo.')
    } finally {
      setSalvando(false)
    }
  }

  return (
    <form className="gaveta-formulario" noValidate onSubmit={(e) => void aoEnviar(e)}>
      <div className="gaveta-conteudo">
        <dl className="dados">
          <dt>Mensalidade</dt>
          <dd>{formatarMoeda(matricula.valor_mensalidade)}</dd>
          <dt>Início</dt>
          <dd>{formatarData(matricula.data_inicio)}</dd>
          <dt>Situação</dt>
          <dd>
            {ativa
              ? 'Ativa'
              : `Encerrada em ${formatarData(matricula.data_encerramento ?? matricula.data_inicio)}`}
          </dd>
        </dl>

        {encerravel && (
          <fieldset className="grupo">
            <legend>Encerrar matrícula</legend>
            <Campo
              id="matricula-encerramento"
              rotulo="Data de encerramento"
              erro={erro}
              dica="O histórico financeiro do aluno é mantido."
            >
              <input
                {...ligacaoDoCampo(
                  'matricula-encerramento',
                  erro,
                  'O histórico financeiro do aluno é mantido.',
                )}
                type="date"
                min={matricula.data_inicio}
                max={hojeIso()}
                value={data}
                onChange={(e) => setData(e.target.value)}
              />
            </Campo>
          </fieldset>
        )}
        {!ativa && (
          <p className="campo-dica">
            Esta matrícula está encerrada. O histórico financeiro continua guardado.
          </p>
        )}
      </div>

      <footer className="gaveta-rodape">
        <span />
        <div className="gaveta-rodape-acoes">
          <button type="button" className="botao botao-texto" onClick={aoFechar}>
            Fechar
          </button>
          {encerravel && (
            <button type="submit" className="botao botao-principal" disabled={salvando}>
              {salvando ? 'Encerrando…' : 'Encerrar matrícula'}
            </button>
          )}
        </div>
      </footer>
    </form>
  )
}

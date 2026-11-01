import { useState, type FormEvent } from 'react'

import { ApiError } from '../../api/client'
import { registrarNota, type Cobranca } from '../../api/cobrancas'
import Campo from '../../components/Campo'
import { ligacaoDoCampo } from '../../utils/campo'
import { formatarData, formatarMoeda, hojeIso, nomeDoMesComMaiuscula } from '../../utils/formato'

type Erros = Partial<Record<'numero' | 'emissao' | 'vencimento' | 'geral', string>>

const NUMERO_MAXIMO = 30
const PRIMEIRA_DATA = '2000-01-01'

/** Soma dias a uma data AAAA-MM-DD, sem depender do fuso horário */
function somarDias(iso: string, dias: number): string {
  const data = new Date(`${iso}T00:00:00Z`)
  data.setUTCDate(data.getUTCDate() + dias)
  return data.toISOString().slice(0, 10)
}

type Props = {
  cobranca: Cobranca
  aoConcluir: (mensagem: string) => void
  aoDesatualizar: () => void
  aoVoltar: () => void
}

/** Registra a nota fiscal (que é emitida fora do sistema) ou corrige a que já foi registrada. */
export default function FormNota({ cobranca, aoConcluir, aoDesatualizar, aoVoltar }: Props) {
  const corrigindo = cobranca.nota !== null
  const [numero, setNumero] = useState(cobranca.nota?.numero_nota ?? '')
  const [emissao, setEmissao] = useState(cobranca.nota?.data_emissao ?? hojeIso())
  // O vencimento já vem sugerido pelo dia combinado com a empresa; dá para mudar
  const [vencimento, setVencimento] = useState(cobranca.data_vencimento)
  const [tentou, setTentou] = useState(false)
  const [salvando, setSalvando] = useState(false)
  const [erroApi, setErroApi] = useState<Erros>({})

  function validar(): Erros {
    const erros: Erros = {}
    const limpo = numero.trim()
    if (!limpo) erros.numero = 'Informe o número da nota.'
    else if (limpo.length > NUMERO_MAXIMO) {
      erros.numero = `Use no máximo ${NUMERO_MAXIMO} caracteres.`
    }
    if (!emissao) erros.emissao = 'Informe a data de emissão.'
    else if (emissao > hojeIso()) erros.emissao = 'A data de emissão não pode ser no futuro.'
    else if (emissao < PRIMEIRA_DATA) erros.emissao = 'Essa data é antiga demais.'
    if (!vencimento) erros.vencimento = 'Informe o vencimento.'
    else if (vencimento < PRIMEIRA_DATA) erros.vencimento = 'Essa data é antiga demais.'
    else if (vencimento < cobranca.competencia) {
      erros.vencimento = 'O vencimento não pode ser antes do mês da cobrança.'
    } else if (emissao && vencimento < emissao) {
      erros.vencimento = 'O vencimento não pode ser antes da emissão da nota.'
    } else if (emissao && vencimento > somarDias(emissao, 366)) {
      erros.vencimento = 'O vencimento deve ser em até um ano depois da emissão.'
    }
    return erros
  }

  const erros: Erros = tentou ? { ...validar(), ...erroApi } : { ...erroApi }

  async function aoEnviar(evento: FormEvent) {
    evento.preventDefault()
    setTentou(true)
    setErroApi({})
    if (Object.keys(validar()).length > 0) return

    setSalvando(true)
    try {
      await registrarNota(cobranca.id, {
        numero_nota: numero.trim(),
        data_emissao: emissao,
        data_vencimento: vencimento,
      })
      aoConcluir(
        corrigindo
          ? `Nota de ${cobranca.padrinho.nome} corrigida`
          : `Nota de ${cobranca.padrinho.nome} registrada`,
      )
    } catch (erro) {
      const campos = erro instanceof ApiError ? erro.campos : {}
      const doServidor: Erros = {}
      if (campos.numero_nota) doServidor.numero = campos.numero_nota
      if (campos.data_emissao) doServidor.emissao = campos.data_emissao
      if (campos.data_vencimento) doServidor.vencimento = campos.data_vencimento
      if (Object.keys(doServidor).length === 0) {
        const mensagem =
          erro instanceof ApiError ? erro.message : 'Não foi possível registrar. Tente de novo.'
        // O número repetido é um problema do campo, não do formulário todo
        if (erro instanceof ApiError && erro.status === 409 && mensagem.includes('número de nota')) {
          doServidor.numero = mensagem
        } else {
          doServidor.geral = mensagem
        }
      }
      if (erro instanceof ApiError && erro.status === 409 && doServidor.geral) aoDesatualizar()
      setErroApi(doServidor)
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
          <dt>Valor da nota</dt>
          <dd>{formatarMoeda(cobranca.valor)}</dd>
          {cobranca.limite_emissao && (
            <>
              <dt>Emitir até</dt>
              <dd>{formatarData(cobranca.limite_emissao)}</dd>
            </>
          )}
        </dl>

        <fieldset className="grupo">
          <legend>{corrigindo ? 'Corrigir a nota' : 'Registrar a nota'}</legend>
          <p className="campo-dica">
            A nota fiscal é emitida fora do sistema. Aqui você só registra o número e as datas.
          </p>
          <Campo id="nota-numero" rotulo="Número da nota" erro={erros.numero}>
            <input
              {...ligacaoDoCampo('nota-numero', erros.numero)}
              autoComplete="off"
              maxLength={NUMERO_MAXIMO}
              value={numero}
              onChange={(e) => setNumero(e.target.value)}
            />
          </Campo>
          <div className="campos-lado-a-lado">
            <Campo id="nota-emissao" rotulo="Data de emissão" erro={erros.emissao}>
              <input
                {...ligacaoDoCampo('nota-emissao', erros.emissao)}
                type="date"
                min={PRIMEIRA_DATA}
                max={hojeIso()}
                value={emissao}
                onChange={(e) => setEmissao(e.target.value)}
              />
            </Campo>
            <Campo id="nota-vencimento" rotulo="Vencimento" erro={erros.vencimento}>
              <input
                {...ligacaoDoCampo('nota-vencimento', erros.vencimento)}
                type="date"
                min={PRIMEIRA_DATA}
                value={vencimento}
                onChange={(e) => setVencimento(e.target.value)}
              />
            </Campo>
          </div>
          <p className="campo-dica">
            O vencimento vem do dia combinado com a empresa. Mude se, desta vez, for outro.
          </p>
        </fieldset>

        {erros.geral && (
          <p className="erro-geral" role="alert">
            {erros.geral}
          </p>
        )}
      </div>

      <footer className="gaveta-rodape">
        <span />
        <div className="gaveta-rodape-acoes">
          <button type="button" className="botao botao-texto" onClick={aoVoltar}>
            Voltar
          </button>
          <button type="submit" className="botao botao-principal" disabled={salvando}>
            {salvando ? 'Registrando…' : corrigindo ? 'Salvar correção' : 'Registrar nota'}
          </button>
        </div>
      </footer>
    </form>
  )
}

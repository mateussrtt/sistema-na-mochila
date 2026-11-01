import { useState, type FormEvent } from 'react'

import { ApiError } from '../../api/client'
import { cancelarMensalidade, isentarMensalidade, type Mensalidade } from '../../api/mensalidades'
import Campo from '../../components/Campo'
import { ligacaoDoCampo } from '../../utils/campo'
import { formatarData, formatarMoeda, nomeDoMesComMaiuscula } from '../../utils/formato'

type Acao = 'isentar' | 'cancelar'
type Erros = Partial<Record<'acao' | 'motivo' | 'geral', string>>

const MOTIVO_MINIMO = 3
const MOTIVO_MAXIMO = 255

const TEXTOS: Record<
  Acao,
  { nome: string; botao: string; fazendo: string; feito: string; explicacao: string }
> = {
  isentar: {
    nome: 'Isentar',
    botao: 'Isentar mensalidade',
    fazendo: 'Isentando…',
    feito: 'isentada',
    explicacao:
      'A família não paga este mês (por exemplo, no recesso). A mensalidade continua no histórico e deixa de contar como cobrança.',
  },
  cancelar: {
    nome: 'Cancelar',
    botao: 'Cancelar mensalidade',
    fazendo: 'Cancelando…',
    feito: 'cancelada',
    explicacao:
      'A mensalidade foi gerada por engano. Ela continua no histórico, mas deixa de ser cobrada.',
  },
}

type Props = {
  mensalidade: Mensalidade
  /** Chamado depois de isentar ou cancelar, com a mensagem de confirmação */
  aoAlterar: (mensagem: string) => void
  /** A API disse que a mensalidade mudou (ex.: já foi paga por outra pessoa): recarrega a lista */
  aoDesatualizar: () => void
  aoVoltar: () => void
}

/**
 * Isentar ou cancelar uma mensalidade pendente, só para o administrador (RF14, RN13).
 * Fica numa tela à parte do pagamento: apertar Enter aqui nunca registra um pagamento.
 */
export default function AlterarMensalidade({
  mensalidade,
  aoAlterar,
  aoDesatualizar,
  aoVoltar,
}: Props) {
  const [acao, setAcao] = useState<Acao | null>(null)
  const [motivo, setMotivo] = useState('')
  const [tentou, setTentou] = useState(false)
  const [salvando, setSalvando] = useState(false)
  const [erroApi, setErroApi] = useState<Erros>({})

  function validar(): Erros {
    const erros: Erros = {}
    if (!acao) erros.acao = 'Escolha entre isentar e cancelar.'
    const limpo = motivo.trim()
    if (!limpo) erros.motivo = 'Informe o motivo.'
    else if (limpo.length < MOTIVO_MINIMO) {
      erros.motivo = `Explique o motivo com pelo menos ${MOTIVO_MINIMO} letras.`
    } else if (limpo.length > MOTIVO_MAXIMO) {
      erros.motivo = `Use no máximo ${MOTIVO_MAXIMO} caracteres.`
    }
    return erros
  }

  const erros: Erros = tentou ? { ...validar(), ...erroApi } : { ...erroApi }

  async function aoEnviar(evento: FormEvent) {
    evento.preventDefault()
    setTentou(true)
    setErroApi({})
    if (!acao || Object.keys(validar()).length > 0) return

    setSalvando(true)
    try {
      const enviar = acao === 'isentar' ? isentarMensalidade : cancelarMensalidade
      await enviar(mensalidade.id, motivo.trim())
      aoAlterar(`Mensalidade de ${mensalidade.aluno.nome} ${TEXTOS[acao].feito}`)
    } catch (erro) {
      const doServidor: Erros = {}
      if (erro instanceof ApiError && erro.campos.motivo) doServidor.motivo = erro.campos.motivo
      if (Object.keys(doServidor).length === 0) {
        doServidor.geral =
          erro instanceof ApiError ? erro.message : 'Não foi possível salvar. Tente de novo.'
      }
      if (erro instanceof ApiError && erro.status === 409) aoDesatualizar()
      setErroApi(doServidor)
    } finally {
      setSalvando(false)
    }
  }

  return (
    <form className="gaveta-formulario" noValidate onSubmit={(e) => void aoEnviar(e)}>
      <div className="gaveta-conteudo">
        <dl className="dados">
          <dt>Aluno</dt>
          <dd>{mensalidade.aluno.nome}</dd>
          <dt>Mês</dt>
          <dd>{nomeDoMesComMaiuscula(mensalidade.competencia.slice(0, 7))}</dd>
          <dt>Valor</dt>
          <dd>{formatarMoeda(mensalidade.valor)}</dd>
          <dt>Vencimento</dt>
          <dd>{formatarData(mensalidade.data_vencimento)}</dd>
        </dl>

        <fieldset className="grupo">
          <legend>Isentar ou cancelar</legend>

          <div className={`campo${erros.acao ? ' com-erro' : ''}`}>
            <span className="rotulo-do-grupo" id="alterar-acao-rotulo">
              O que fazer com esta mensalidade?
            </span>
            <div
              className="segmentos segmentos-largos"
              role="group"
              aria-labelledby="alterar-acao-rotulo"
            >
              {(['isentar', 'cancelar'] as const).map((a) => (
                <button key={a} type="button" aria-pressed={acao === a} onClick={() => setAcao(a)}>
                  {TEXTOS[a].nome}
                </button>
              ))}
            </div>
            {acao && <p className="campo-dica">{TEXTOS[acao].explicacao}</p>}
            {erros.acao && (
              <p className="campo-erro" id="alterar-acao-erro" role="alert">
                {erros.acao}
              </p>
            )}
          </div>

          <Campo
            id="alterar-motivo"
            rotulo="Motivo"
            erro={erros.motivo}
            dica="Escreva só o necessário: o motivo fica registrado com o seu nome e pode ser visto por quem usa o sistema."
          >
            <input
              {...ligacaoDoCampo(
                'alterar-motivo',
                erros.motivo,
                'Escreva só o necessário: o motivo fica registrado com o seu nome e pode ser visto por quem usa o sistema.',
              )}
              autoComplete="off"
              maxLength={MOTIVO_MAXIMO}
              value={motivo}
              onChange={(e) => setMotivo(e.target.value)}
            />
          </Campo>

          <p className="aviso-valor" role="note">
            Isto não pode ser desfeito pela tela. A mensalidade não é apagada: continua na lista com
            o motivo.
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
          <button type="submit" className="botao botao-perigo" disabled={salvando}>
            {salvando ? (acao ? TEXTOS[acao].fazendo : 'Salvando…') : acao ? TEXTOS[acao].botao : 'Confirmar'}
          </button>
        </div>
      </footer>
    </form>
  )
}

import { useState, type FormEvent } from 'react'

import { ApiError } from '../../api/client'
import {
  NOME_DA_FORMA,
  NOME_DA_SITUACAO,
  registrarPagamento,
  type FormaDePagamento,
  type Mensalidade,
} from '../../api/mensalidades'
import Campo from '../../components/Campo'
import { useSessao } from '../../sessao/contexto'
import { ligacaoDoCampo } from '../../utils/campo'
import {
  emCentavos,
  formatarData,
  formatarDataHora,
  formatarMoeda,
  hojeIso,
  lerValor,
  nomeDoMes,
} from '../../utils/formato'

type Props = {
  mensalidade: Mensalidade
  /** Chamado depois de registrar o pagamento, com a mensagem de confirmação */
  aoPagar: (mensagem: string) => void
  /** A API disse que a mensalidade mudou (ex.: já foi paga por outra pessoa): recarrega a lista */
  aoDesatualizar: () => void
  aoFechar: () => void
}

type Erros = Partial<Record<'data' | 'valor' | 'forma' | 'observacao' | 'geral', string>>

const FORMAS: FormaDePagamento[] = ['pix', 'dinheiro', 'boleto', 'outra']
const PRIMEIRA_DATA = '2000-01-01'
const OBSERVACAO_MAXIMA = 255

function erroDoValor(texto: string): string | undefined {
  const limpo = texto.trim()
  if (!limpo) return 'Informe o valor pago.'
  if (limpo.startsWith('-')) return 'O valor pago deve ser maior que zero.'
  const valor = lerValor(limpo)
  if (valor === null) return 'Use só números, com até 2 casas decimais. Ex.: 150,00'
  if (valor <= 0) return 'O valor pago deve ser maior que zero.'
  if (valor >= 100_000_000) return 'O valor pago é alto demais.'
}

/** Dados da mensalidade. Pendente: registra o pagamento. Paga: mostra o que foi registrado. */
export default function DetalheMensalidade({
  mensalidade,
  aoPagar,
  aoDesatualizar,
  aoFechar,
}: Props) {
  const { podeEditar } = useSessao()
  const [data, setData] = useState(hojeIso())
  const [valor, setValor] = useState(mensalidade.valor.replace('.', ','))
  const [forma, setForma] = useState<FormaDePagamento | null>(null)
  const [observacao, setObservacao] = useState('')
  const [tentou, setTentou] = useState(false)
  const [salvando, setSalvando] = useState(false)
  const [erroApi, setErroApi] = useState<Erros>({})

  const pendente = mensalidade.status === 'pendente'
  const registravel = pendente && podeEditar
  const pagamento = mensalidade.pagamento

  const valorLido = lerValor(valor.trim())
  const diferente = valorLido !== null && emCentavos(valorLido) !== emCentavos(mensalidade.valor)

  function validar(): Erros {
    const erros: Erros = {}
    if (!data) erros.data = 'Informe a data do pagamento.'
    else if (data > hojeIso()) erros.data = 'A data do pagamento não pode ser no futuro.'
    else if (data < PRIMEIRA_DATA) erros.data = 'Essa data é antiga demais.'
    const erroValor = erroDoValor(valor)
    if (erroValor) erros.valor = erroValor
    if (!forma) erros.forma = 'Escolha como foi pago.'
    if (diferente && !observacao.trim()) {
      erros.observacao = 'Explique por que o valor é diferente do previsto.'
    }
    if (observacao.trim().length > OBSERVACAO_MAXIMA) {
      erros.observacao = `Use no máximo ${OBSERVACAO_MAXIMA} caracteres.`
    }
    return erros
  }

  const erros: Erros = tentou ? { ...validar(), ...erroApi } : { ...erroApi }

  async function aoEnviar(evento: FormEvent) {
    evento.preventDefault()
    setTentou(true)
    setErroApi({})
    if (!forma || Object.keys(validar()).length > 0) return

    setSalvando(true)
    try {
      await registrarPagamento(mensalidade.id, {
        data_pagamento: data,
        valor_pago: valor.trim().replace(',', '.'),
        forma_pagamento: forma,
        observacao: observacao.trim(),
      })
      aoPagar(`Pagamento de ${mensalidade.aluno.nome} registrado`)
    } catch (erro) {
      const campos = erro instanceof ApiError ? erro.campos : {}
      const doServidor: Erros = {}
      if (campos.data_pagamento) doServidor.data = campos.data_pagamento
      if (campos.valor_pago) doServidor.valor = campos.valor_pago
      if (campos.forma_pagamento) doServidor.forma = campos.forma_pagamento
      if (campos.observacao) doServidor.observacao = campos.observacao
      if (Object.keys(doServidor).length === 0) {
        doServidor.geral =
          erro instanceof ApiError ? erro.message : 'Não foi possível registrar. Tente de novo.'
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
          <dd className="primeira-maiuscula">{nomeDoMes(mensalidade.competencia.slice(0, 7))}</dd>
          <dt>Valor</dt>
          <dd>{formatarMoeda(mensalidade.valor)}</dd>
          <dt>Vencimento</dt>
          <dd>{formatarData(mensalidade.data_vencimento)}</dd>
          <dt>Situação</dt>
          <dd>
            {NOME_DA_SITUACAO[mensalidade.situacao]}
            {mensalidade.situacao === 'atrasada' &&
              ` (${mensalidade.dias_em_atraso} ${mensalidade.dias_em_atraso === 1 ? 'dia' : 'dias'})`}
          </dd>
        </dl>

        {pagamento && (
          <fieldset className="grupo">
            <legend>Pagamento</legend>
            <dl className="dados">
              <dt>Pago em</dt>
              <dd>{formatarData(pagamento.data_pagamento)}</dd>
              <dt>Valor pago</dt>
              <dd>{formatarMoeda(pagamento.valor_pago)}</dd>
              <dt>Forma</dt>
              <dd>{NOME_DA_FORMA[pagamento.forma_pagamento]}</dd>
              {pagamento.observacao && (
                <>
                  <dt>Observação</dt>
                  <dd>{pagamento.observacao}</dd>
                </>
              )}
              <dt>Registrado por</dt>
              <dd>
                {pagamento.registrado_por}, em {formatarDataHora(pagamento.registrado_em)}
              </dd>
            </dl>
          </fieldset>
        )}

        {registravel && (
          <fieldset className="grupo">
            <legend>Registrar pagamento</legend>
            <div className="campos-lado-a-lado">
              <Campo id="pagamento-data" rotulo="Data do pagamento" erro={erros.data}>
                <input
                  {...ligacaoDoCampo('pagamento-data', erros.data)}
                  type="date"
                  min={PRIMEIRA_DATA}
                  max={hojeIso()}
                  value={data}
                  onChange={(e) => setData(e.target.value)}
                />
              </Campo>
              <Campo id="pagamento-valor" rotulo="Valor pago (R$)" erro={erros.valor}>
                <input
                  {...ligacaoDoCampo('pagamento-valor', erros.valor)}
                  inputMode="decimal"
                  placeholder="0,00"
                  autoComplete="off"
                  value={valor}
                  onChange={(e) => setValor(e.target.value)}
                />
              </Campo>
            </div>

            <div className={`campo${erros.forma ? ' com-erro' : ''}`}>
              <span className="rotulo-do-grupo" id="pagamento-forma-rotulo">
                Forma de pagamento
              </span>
              <div
                className="segmentos segmentos-forma"
                role="group"
                aria-labelledby="pagamento-forma-rotulo"
              >
                {FORMAS.map((f) => (
                  <button key={f} type="button" aria-pressed={forma === f} onClick={() => setForma(f)}>
                    {NOME_DA_FORMA[f]}
                  </button>
                ))}
              </div>
              {erros.forma && (
                <p className="campo-erro" id="pagamento-forma-erro" role="alert">
                  {erros.forma}
                </p>
              )}
            </div>

            {diferente && (
              <p className="aviso-valor" role="status">
                O valor é diferente do previsto ({formatarMoeda(mensalidade.valor)}). Explique o
                motivo na observação.
              </p>
            )}
            <Campo
              id="pagamento-observacao"
              rotulo="Observação"
              opcional={!diferente}
              erro={erros.observacao}
            >
              <input
                {...ligacaoDoCampo('pagamento-observacao', erros.observacao)}
                autoComplete="off"
                maxLength={OBSERVACAO_MAXIMA}
                value={observacao}
                onChange={(e) => setObservacao(e.target.value)}
              />
            </Campo>
          </fieldset>
        )}

        {!pagamento && !registravel && (
          <p className="campo-dica">
            {pendente
              ? 'Seu perfil só consulta: o pagamento é registrado por um operador ou administrador.'
              : 'Esta mensalidade não recebe pagamento.'}
          </p>
        )}

        {erros.geral && (
          <p className="erro-geral" role="alert">
            {erros.geral}
          </p>
        )}
      </div>

      <footer className="gaveta-rodape">
        <span />
        <div className="gaveta-rodape-acoes">
          <button type="button" className="botao botao-texto" onClick={aoFechar}>
            {registravel ? 'Cancelar' : 'Fechar'}
          </button>
          {registravel && (
            <button type="submit" className="botao botao-principal" disabled={salvando}>
              {salvando ? 'Registrando…' : 'Registrar pagamento'}
            </button>
          )}
        </div>
      </footer>
    </form>
  )
}

import { useState, type FormEvent } from 'react'

import { ApiError } from '../../api/client'
import {
  NOME_DA_FORMA_COBRANCA,
  registrarPagamentoDaCobranca,
  type Cobranca,
  type FormaDePagamentoCobranca,
} from '../../api/cobrancas'
import Campo from '../../components/Campo'
import { ligacaoDoCampo } from '../../utils/campo'
import {
  emCentavos,
  formatarData,
  formatarMoeda,
  hojeIso,
  lerValor,
  nomeDoMesComMaiuscula,
} from '../../utils/formato'

type Erros = Partial<Record<'data' | 'valor' | 'forma' | 'observacao' | 'geral', string>>

const FORMAS: FormaDePagamentoCobranca[] = ['pix', 'transferencia', 'boleto', 'outra']
const PRIMEIRA_DATA = '2000-01-01'
const OBSERVACAO_MAXIMA = 255

function erroDoValor(texto: string): string | undefined {
  const limpo = texto.trim()
  if (!limpo) return 'Informe o valor pago.'
  if (limpo.startsWith('-')) return 'O valor pago deve ser maior que zero.'
  const valor = lerValor(limpo)
  if (valor === null) return 'Use só números, com até 2 casas decimais. Ex.: 450,00'
  if (valor <= 0) return 'O valor pago deve ser maior que zero.'
  if (valor >= 100_000_000) return 'O valor pago é alto demais.'
}

type Props = {
  cobranca: Cobranca
  aoConcluir: (mensagem: string) => void
  aoDesatualizar: () => void
  aoVoltar: () => void
}

/** Registra o pagamento da empresa: a cobrança e as mensalidades dos alunos ficam quitadas. */
export default function FormPagamentoCobranca({
  cobranca,
  aoConcluir,
  aoDesatualizar,
  aoVoltar,
}: Props) {
  const [data, setData] = useState(hojeIso())
  const [valor, setValor] = useState(cobranca.valor.replace('.', ','))
  // Nenhuma forma vem marcada: quem registra escolhe de propósito
  const [forma, setForma] = useState<FormaDePagamentoCobranca | null>(null)
  const [observacao, setObservacao] = useState('')
  const [tentou, setTentou] = useState(false)
  const [salvando, setSalvando] = useState(false)
  const [erroApi, setErroApi] = useState<Erros>({})

  const valorLido = lerValor(valor.trim())
  const diferente = valorLido !== null && emCentavos(valorLido) !== emCentavos(cobranca.valor)

  function validar(): Erros {
    const erros: Erros = {}
    if (!data) erros.data = 'Informe a data do pagamento.'
    else if (data > hojeIso()) erros.data = 'A data do pagamento não pode ser no futuro.'
    else if (data < PRIMEIRA_DATA) erros.data = 'Essa data é antiga demais.'
    const erroValor = erroDoValor(valor)
    if (erroValor) erros.valor = erroValor
    if (!forma) erros.forma = 'Escolha como foi pago.'
    if (diferente && !observacao.trim()) {
      erros.observacao = 'Explique por que o valor é diferente do cobrado.'
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
      await registrarPagamentoDaCobranca(cobranca.id, {
        data_pagamento: data,
        valor_pago: valor.trim().replace(',', '.'),
        forma_pagamento: forma,
        observacao: observacao.trim(),
      })
      aoConcluir(`Pagamento de ${cobranca.padrinho.nome} registrado`)
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
          <dt>Empresa</dt>
          <dd>{cobranca.padrinho.nome}</dd>
          <dt>Mês</dt>
          <dd>{nomeDoMesComMaiuscula(cobranca.competencia.slice(0, 7))}</dd>
          <dt>Nota</dt>
          <dd>{cobranca.nota?.numero_nota}</dd>
          <dt>Valor cobrado</dt>
          <dd>{formatarMoeda(cobranca.valor)}</dd>
          <dt>Vencimento</dt>
          <dd>{formatarData(cobranca.data_vencimento)}</dd>
        </dl>

        <fieldset className="grupo">
          <legend>Registrar pagamento</legend>
          <p className="campo-dica">
            Ao registrar, as mensalidades dos {cobranca.alunos.length} alunos da cobrança ficam
            quitadas.
          </p>
          <div className="campos-lado-a-lado">
            <Campo id="cobranca-data" rotulo="Data do pagamento" erro={erros.data}>
              <input
                {...ligacaoDoCampo('cobranca-data', erros.data)}
                type="date"
                min={PRIMEIRA_DATA}
                max={hojeIso()}
                value={data}
                onChange={(e) => setData(e.target.value)}
              />
            </Campo>
            <Campo id="cobranca-valor" rotulo="Valor pago (R$)" erro={erros.valor}>
              <input
                {...ligacaoDoCampo('cobranca-valor', erros.valor)}
                inputMode="decimal"
                placeholder="0,00"
                autoComplete="off"
                value={valor}
                onChange={(e) => setValor(e.target.value)}
              />
            </Campo>
          </div>

          <div className={`campo${erros.forma ? ' com-erro' : ''}`}>
            <span className="rotulo-do-grupo" id="cobranca-forma-rotulo">
              Forma de pagamento
            </span>
            <div
              className="segmentos segmentos-quatro"
              role="group"
              aria-labelledby="cobranca-forma-rotulo"
            >
              {FORMAS.map((f) => (
                <button key={f} type="button" aria-pressed={forma === f} onClick={() => setForma(f)}>
                  {NOME_DA_FORMA_COBRANCA[f]}
                </button>
              ))}
            </div>
            {erros.forma && (
              <p className="campo-erro" id="cobranca-forma-erro" role="alert">
                {erros.forma}
              </p>
            )}
          </div>

          {diferente && (
            <p className="aviso-valor" role="status">
              O valor é diferente do cobrado ({formatarMoeda(cobranca.valor)}). Explique o motivo na
              observação.
            </p>
          )}
          <Campo
            id="cobranca-observacao"
            rotulo="Observação"
            opcional={!diferente}
            erro={erros.observacao}
          >
            <input
              {...ligacaoDoCampo('cobranca-observacao', erros.observacao)}
              autoComplete="off"
              maxLength={OBSERVACAO_MAXIMA}
              value={observacao}
              onChange={(e) => setObservacao(e.target.value)}
            />
          </Campo>
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
            {salvando ? 'Registrando…' : 'Registrar pagamento'}
          </button>
        </div>
      </footer>
    </form>
  )
}

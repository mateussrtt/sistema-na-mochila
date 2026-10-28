import { X } from 'lucide-react'
import { useState, type FormEvent } from 'react'

import { matricularAluno, NOME_DA_BOLSA, type Aluno, type Bolsa } from '../../api/cadastros'
import { ApiError } from '../../api/client'
import Campo from '../../components/Campo'
import Monograma from '../../components/Monograma'
import { ligacaoDoCampo } from '../../utils/campo'
import { hojeIso, lerValor } from '../../utils/formato'
import SeletorAluno from './SeletorAluno'

type Props = {
  aoSalvar: (mensagem: string) => void
  aoCancelar: () => void
}

type Erros = Partial<Record<'aluno' | 'data_inicio' | 'valor' | 'geral', string>>

const BOLSAS: Bolsa[] = ['nenhuma', 'parcial', 'integral']

function erroDoValor(texto: string): string | undefined {
  const limpo = texto.trim()
  if (!limpo) return 'Informe o valor da mensalidade.'
  if (limpo.startsWith('-')) return 'O valor da mensalidade deve ser maior que zero.'
  const valor = lerValor(limpo)
  if (valor === null) return 'Use só números, com até 2 casas decimais. Ex.: 150,00'
  if (valor <= 0) return 'O valor da mensalidade deve ser maior que zero.'
}

export default function FormMatricula({ aoSalvar, aoCancelar }: Props) {
  const [aluno, setAluno] = useState<Aluno | null>(null)
  const [inicio, setInicio] = useState(hojeIso())
  const [valor, setValor] = useState('')
  const [bolsa, setBolsa] = useState<Bolsa>('nenhuma')
  const integral = bolsa === 'integral'
  const [tentou, setTentou] = useState(false)
  const [salvando, setSalvando] = useState(false)
  const [erroApi, setErroApi] = useState<Erros>({})

  function validar(): Erros {
    const erros: Erros = {}
    if (!aluno) erros.aluno = 'Escolha o aluno que será matriculado.'
    if (!inicio) erros.data_inicio = 'Informe a data de início.'
    const erroValor = integral ? undefined : erroDoValor(valor)
    if (erroValor) erros.valor = erroValor
    return erros
  }

  const erros: Erros = tentou ? { ...validar(), ...erroApi } : {}

  async function aoEnviar(evento: FormEvent) {
    evento.preventDefault()
    setTentou(true)
    setErroApi({})
    if (!aluno || Object.keys(validar()).length > 0) return

    setSalvando(true)
    try {
      await matricularAluno({
        aluno_id: aluno.id,
        data_inicio: inicio,
        bolsa,
        valor_mensalidade: integral ? '0' : valor.trim().replace(',', '.'),
      })
      aoSalvar(integral ? 'Matrícula com bolsa integral registrada' : 'Matrícula registrada')
    } catch (erro) {
      const campos = erro instanceof ApiError ? erro.campos : {}
      const doServidor: Erros = {}
      if (campos.data_inicio) doServidor.data_inicio = campos.data_inicio
      if (campos.valor_mensalidade) doServidor.valor = campos.valor_mensalidade
      if (Object.keys(doServidor).length === 0) {
        doServidor.geral =
          erro instanceof ApiError ? erro.message : 'Não foi possível salvar. Tente de novo.'
      }
      setErroApi(doServidor)
    } finally {
      setSalvando(false)
    }
  }

  return (
    <form className="gaveta-formulario" noValidate onSubmit={(e) => void aoEnviar(e)}>
      <div className="gaveta-conteudo">
        <fieldset className={`grupo grupo-inicial${erros.aluno ? ' com-erro' : ''}`}>
          <legend>Aluno</legend>
          {aluno ? (
            <ul className="vinculados">
              <li>
                <Monograma nome={aluno.nome} tamanho="p" />
                <span className="pessoa-texto">
                  <strong>{aluno.nome}</strong>
                  <span>{[aluno.escola, aluno.municipio].filter(Boolean).join(', ')}</span>
                </span>
                <button
                  type="button"
                  className="botao-icone"
                  aria-label={`Trocar ${aluno.nome}`}
                  onClick={() => setAluno(null)}
                >
                  <X size={18} />
                </button>
              </li>
            </ul>
          ) : (
            <>
              <SeletorAluno aoEscolher={setAluno} invalido={Boolean(erros.aluno)} />
              {erros.aluno && (
                <p className="campo-erro" id="aluno-erro" role="alert">
                  {erros.aluno}
                </p>
              )}
            </>
          )}
        </fieldset>

        <fieldset className="grupo">
          <legend>Bolsa</legend>
          <div className="segmentos segmentos-largos" role="group" aria-label="Bolsa">
            {BOLSAS.map((b) => (
              <button key={b} type="button" aria-pressed={bolsa === b} onClick={() => setBolsa(b)}>
                {NOME_DA_BOLSA[b]}
              </button>
            ))}
          </div>
          <p className="campo-dica">
            {bolsa === 'nenhuma' && 'O aluno paga o valor cheio da mensalidade.'}
            {bolsa === 'parcial' && 'Informe abaixo o valor que a família paga, já com o desconto.'}
            {integral && 'Bolsista integral não paga mensalidade e não entra nas cobranças.'}
          </p>
        </fieldset>

        <div className="campos-lado-a-lado">
          <Campo id="matricula-inicio" rotulo="Data de início" erro={erros.data_inicio}>
            <input
              {...ligacaoDoCampo('matricula-inicio', erros.data_inicio)}
              type="date"
              value={inicio}
              onChange={(e) => setInicio(e.target.value)}
            />
          </Campo>
          <Campo
            id="matricula-valor"
            rotulo={bolsa === 'parcial' ? 'Valor com desconto (R$)' : 'Valor da mensalidade (R$)'}
            erro={erros.valor}
          >
            <input
              {...ligacaoDoCampo('matricula-valor', erros.valor)}
              inputMode="decimal"
              placeholder="0,00"
              autoComplete="off"
              disabled={integral}
              value={integral ? '0,00' : valor}
              onChange={(e) => setValor(e.target.value)}
            />
          </Campo>
        </div>

        {erros.geral && (
          <p className="erro-geral" role="alert">
            {erros.geral}
          </p>
        )}
      </div>

      <footer className="gaveta-rodape">
        <span />
        <div className="gaveta-rodape-acoes">
          <button type="button" className="botao botao-texto" onClick={aoCancelar}>
            Cancelar
          </button>
          <button type="submit" className="botao botao-principal" disabled={salvando}>
            {salvando ? 'Salvando…' : 'Matricular aluno'}
          </button>
        </div>
      </footer>
    </form>
  )
}

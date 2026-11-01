import { Archive, ArchiveRestore } from 'lucide-react'
import { useState, type FormEvent } from 'react'

import { ApiError } from '../../api/client'
import { salvarPadrinho, type Padrinho } from '../../api/padrinhos'
import Campo from '../../components/Campo'
import { useSessao } from '../../sessao/contexto'
import { ligacaoDoCampo } from '../../utils/campo'
import {
  cnpjValido,
  emailValido,
  mascaraCnpj,
  mascaraTelefone,
  telefoneValido,
} from '../../utils/formato'

type Props = {
  padrinho?: Padrinho
  aoSalvar: (mensagem: string) => void
  aoCancelar: () => void
}

type Erros = Partial<
  Record<
    'nome' | 'cnpj' | 'contato' | 'telefone' | 'email' | 'vencimento' | 'emitir' | 'geral',
    string
  >
>

const DIA_MAXIMO = 28

/** Só números, no máximo 2 dígitos: o dia do mês */
function soDia(texto: string): string {
  return texto.replace(/\D/g, '').slice(0, 2)
}

export default function FormPadrinho({ padrinho, aoSalvar, aoCancelar }: Props) {
  const { podeEditar } = useSessao()
  const [nome, setNome] = useState(padrinho?.nome ?? '')
  const [cnpj, setCnpj] = useState(mascaraCnpj(padrinho?.cnpj ?? ''))
  const [contato, setContato] = useState(padrinho?.contato ?? '')
  const [telefone, setTelefone] = useState(mascaraTelefone(padrinho?.telefone ?? ''))
  const [email, setEmail] = useState(padrinho?.email ?? '')
  const [vencimento, setVencimento] = useState(padrinho ? String(padrinho.dia_vencimento) : '')
  const [emitir, setEmitir] = useState(padrinho?.emitir_ate_dia ? String(padrinho.emitir_ate_dia) : '')
  const [tentou, setTentou] = useState(false)
  const [salvando, setSalvando] = useState(false)
  const [erroApi, setErroApi] = useState<Erros>({})

  function validar(): Erros {
    const erros: Erros = {}
    if (nome.trim().length < 2) erros.nome = 'Informe o nome da empresa.'
    if (cnpj.trim() && !cnpjValido(cnpj)) erros.cnpj = 'CNPJ inválido. Confira os números.'
    if (!telefone.trim()) erros.telefone = 'Informe o telefone de contato.'
    else if (!telefoneValido(telefone)) {
      erros.telefone = 'Use DDD e número, como (31) 98888-7777.'
    }
    if (!email.trim()) erros.email = 'Informe o e-mail de contato.'
    else if (!emailValido(email)) erros.email = 'Confira o e-mail, como nome@exemplo.com.'

    const diaVencimento = Number(vencimento)
    if (!vencimento) erros.vencimento = 'Informe o dia do vencimento.'
    else if (diaVencimento < 1 || diaVencimento > DIA_MAXIMO) {
      erros.vencimento = `Use um dia de 1 a ${DIA_MAXIMO}.`
    }
    if (emitir) {
      const diaNota = Number(emitir)
      if (diaNota < 1 || diaNota > DIA_MAXIMO) erros.emitir = `Use um dia de 1 a ${DIA_MAXIMO}.`
      else if (!erros.vencimento && diaNota > diaVencimento) {
        erros.emitir = 'A nota deve ser emitida até o dia do vencimento, no máximo.'
      }
    }
    return erros
  }

  const erros: Erros = tentou ? { ...validar(), ...erroApi } : {}

  async function enviar(ativo: boolean, mensagem: string) {
    setTentou(true)
    setErroApi({})
    if (Object.keys(validar()).length > 0) return

    setSalvando(true)
    try {
      await salvarPadrinho(
        {
          nome,
          cnpj,
          contato,
          telefone,
          email,
          dia_vencimento: Number(vencimento),
          emitir_ate_dia: emitir ? Number(emitir) : null,
          ativo,
        },
        padrinho?.id,
      )
      aoSalvar(mensagem)
    } catch (erro) {
      const api = erro instanceof ApiError ? erro : null
      const campos = api?.campos ?? {}
      const doServidor: Erros = {}
      if (campos.nome) doServidor.nome = campos.nome
      if (campos.cnpj) doServidor.cnpj = campos.cnpj
      if (campos.contato) doServidor.contato = campos.contato
      if (campos.telefone) doServidor.telefone = campos.telefone
      if (campos.email) doServidor.email = campos.email
      if (campos.dia_vencimento) doServidor.vencimento = campos.dia_vencimento
      if (campos.emitir_ate_dia) doServidor.emitir = campos.emitir_ate_dia
      // O CNPJ repetido volta como erro geral (409): mostra junto do campo certo
      if (api?.status === 409) doServidor.cnpj = api.message
      if (Object.keys(doServidor).length === 0) {
        doServidor.geral = api?.message ?? 'Não foi possível salvar. Tente de novo.'
      }
      setErroApi(doServidor)
    } finally {
      setSalvando(false)
    }
  }

  function aoEnviar(evento: FormEvent) {
    evento.preventDefault()
    void enviar(padrinho?.ativo ?? true, padrinho ? 'Alterações salvas' : 'Padrinho cadastrado')
  }

  return (
    <form className="gaveta-formulario" noValidate onSubmit={aoEnviar}>
      <fieldset className="gaveta-conteudo" disabled={!podeEditar}>
        <Campo id="padrinho-nome" rotulo="Nome da empresa" erro={erros.nome}>
          <input
            {...ligacaoDoCampo('padrinho-nome', erros.nome)}
            value={nome}
            maxLength={120}
            autoComplete="off"
            onChange={(e) => setNome(e.target.value)}
          />
        </Campo>

        <Campo id="padrinho-cnpj" rotulo="CNPJ" erro={erros.cnpj} opcional>
          <input
            {...ligacaoDoCampo('padrinho-cnpj', erros.cnpj)}
            value={cnpj}
            placeholder="00.000.000/0000-00"
            autoComplete="off"
            onChange={(e) => setCnpj(mascaraCnpj(e.target.value))}
          />
        </Campo>

        <fieldset className="grupo">
          <legend>Contato na empresa</legend>
          <Campo id="padrinho-contato" rotulo="Pessoa de contato" erro={erros.contato} opcional>
            <input
              {...ligacaoDoCampo('padrinho-contato', erros.contato)}
              value={contato}
              maxLength={120}
              autoComplete="off"
              onChange={(e) => setContato(e.target.value)}
            />
          </Campo>
          <div className="campos-lado-a-lado">
            <Campo id="padrinho-telefone" rotulo="Telefone" erro={erros.telefone}>
              <input
                {...ligacaoDoCampo('padrinho-telefone', erros.telefone)}
                type="tel"
                inputMode="tel"
                value={telefone}
                placeholder="(31) 98888-7777"
                onChange={(e) => setTelefone(mascaraTelefone(e.target.value))}
              />
            </Campo>
            <Campo id="padrinho-email" rotulo="E-mail" erro={erros.email}>
              <input
                {...ligacaoDoCampo('padrinho-email', erros.email)}
                type="email"
                inputMode="email"
                value={email}
                placeholder="financeiro@empresa.com"
                onChange={(e) => setEmail(e.target.value)}
              />
            </Campo>
          </div>
          <p className="nota">O telefone e o e-mail são obrigatórios: é por eles que a empresa é procurada.</p>
        </fieldset>

        <fieldset className="grupo">
          <legend>Datas combinadas</legend>
          <div className="campos-lado-a-lado">
            <Campo id="padrinho-vencimento" rotulo="Dia do vencimento" erro={erros.vencimento}>
              <input
                {...ligacaoDoCampo('padrinho-vencimento', erros.vencimento)}
                inputMode="numeric"
                value={vencimento}
                placeholder="Ex.: 25"
                autoComplete="off"
                onChange={(e) => setVencimento(soDia(e.target.value))}
              />
            </Campo>
            <Campo id="padrinho-emitir" rotulo="Emitir a nota até o dia" erro={erros.emitir} opcional>
              <input
                {...ligacaoDoCampo('padrinho-emitir', erros.emitir)}
                inputMode="numeric"
                value={emitir}
                placeholder="Ex.: 10"
                autoComplete="off"
                onChange={(e) => setEmitir(soDia(e.target.value))}
              />
            </Campo>
          </div>
          <p className="nota">
            Dias de 1 a {DIA_MAXIMO}. Exemplo: nota emitida até o dia 10 e vencimento no dia 25.
          </p>
        </fieldset>

        {erros.geral && (
          <p className="erro-geral" role="alert">
            {erros.geral}
          </p>
        )}
      </fieldset>

      <footer className="gaveta-rodape">
        {padrinho && podeEditar ? (
          <button
            type="button"
            className="botao botao-texto botao-com-icone"
            disabled={salvando}
            onClick={() =>
              void enviar(
                !padrinho.ativo,
                padrinho.ativo ? 'Padrinho inativado' : 'Padrinho reativado',
              )
            }
          >
            {padrinho.ativo ? (
              <Archive size={18} aria-hidden="true" />
            ) : (
              <ArchiveRestore size={18} aria-hidden="true" />
            )}
            {padrinho.ativo ? 'Inativar padrinho' : 'Reativar padrinho'}
          </button>
        ) : (
          <span />
        )}
        <div className="gaveta-rodape-acoes">
          <button type="button" className="botao botao-texto" onClick={aoCancelar}>
            {podeEditar ? 'Cancelar' : 'Fechar'}
          </button>
          {podeEditar && (
            <button type="submit" className="botao botao-principal" disabled={salvando}>
              {salvando ? 'Salvando…' : padrinho ? 'Salvar alterações' : 'Cadastrar padrinho'}
            </button>
          )}
        </div>
      </footer>
    </form>
  )
}

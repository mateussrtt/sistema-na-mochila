import { useState, type FormEvent, type KeyboardEvent } from 'react'

import { salvarResponsavel, type Responsavel } from '../../api/cadastros'
import { ApiError } from '../../api/client'
import Campo from '../../components/Campo'
import { useSessao } from '../../sessao/contexto'
import { ligacaoDoCampo } from '../../utils/campo'
import { emailValido, mascaraTelefone, telefoneValido } from '../../utils/formato'

type Props = {
  responsavel?: Responsavel
  /** Versão menor, usada dentro do cadastro de aluno */
  compacto?: boolean
  nomeInicial?: string
  aoSalvar: (responsavel: Responsavel) => void
  aoCancelar: () => void
}

type Erros = Partial<Record<'nome' | 'telefone' | 'email', string>>

function validar(nome: string, telefone: string, email: string): Erros {
  const erros: Erros = {}
  if (nome.trim().length < 2) erros.nome = 'Informe o nome do responsável.'
  if (telefone && !telefoneValido(telefone)) {
    erros.telefone = 'Use DDD e número, como (31) 98888-7777.'
  }
  if (email && !emailValido(email)) erros.email = 'Confira o e-mail, como nome@exemplo.com.'
  if (!telefone.trim() && !email.trim()) {
    erros.telefone = 'Informe um telefone ou um e-mail para contato.'
  }
  return erros
}

export default function FormResponsavel({
  responsavel,
  compacto = false,
  nomeInicial = '',
  aoSalvar,
  aoCancelar,
}: Props) {
  const { podeEditar } = useSessao()
  const [nome, setNome] = useState(responsavel?.nome ?? nomeInicial)
  const [telefone, setTelefone] = useState(mascaraTelefone(responsavel?.telefone ?? ''))
  const [email, setEmail] = useState(responsavel?.email ?? '')
  const [tentou, setTentou] = useState(false)
  const [salvando, setSalvando] = useState(false)
  const [erroApi, setErroApi] = useState<{ geral?: string } & Erros>({})

  const erros: Erros = tentou ? { ...validar(nome, telefone, email), ...erroApi } : {}
  const prefixo = compacto ? 'novo-responsavel' : 'responsavel'

  async function salvar() {
    setTentou(true)
    setErroApi({})
    if (Object.keys(validar(nome, telefone, email)).length > 0) return

    setSalvando(true)
    try {
      aoSalvar(await salvarResponsavel({ nome, telefone, email }, responsavel?.id))
    } catch (erro) {
      const api = erro instanceof ApiError ? erro : null
      const campos = api?.campos ?? {}
      const temErroDeCampo = Boolean(campos.nome || campos.telefone || campos.email)
      const geral = api?.message ?? 'Não foi possível salvar. Tente de novo.'
      setErroApi({ ...campos, geral: temErroDeCampo ? undefined : geral })
    } finally {
      setSalvando(false)
    }
  }

  function aoEnviar(evento: FormEvent) {
    evento.preventDefault()
    void salvar()
  }

  // Dentro do formulário de aluno, Enter salva só o responsável, não o aluno inteiro
  function aoTeclar(evento: KeyboardEvent) {
    if (compacto && evento.key === 'Enter') {
      evento.preventDefault()
      void salvar()
    }
  }

  const campos = (
    <>
      <Campo id={`${prefixo}-nome`} rotulo="Nome" erro={erros.nome}>
        <input
          {...ligacaoDoCampo(`${prefixo}-nome`, erros.nome)}
          value={nome}
          autoComplete="off"
          autoFocus={compacto}
          onKeyDown={aoTeclar}
          onChange={(e) => setNome(e.target.value)}
        />
      </Campo>
      <div className="campos-lado-a-lado">
        <Campo id={`${prefixo}-telefone`} rotulo="Telefone" erro={erros.telefone}>
          <input
            {...ligacaoDoCampo(`${prefixo}-telefone`, erros.telefone)}
            type="tel"
            inputMode="tel"
            value={telefone}
            placeholder="(31) 98888-7777"
            onKeyDown={aoTeclar}
            onChange={(e) => setTelefone(mascaraTelefone(e.target.value))}
          />
        </Campo>
        <Campo id={`${prefixo}-email`} rotulo="E-mail" erro={erros.email}>
          <input
            {...ligacaoDoCampo(`${prefixo}-email`, erros.email)}
            type="email"
            inputMode="email"
            value={email}
            placeholder="nome@exemplo.com"
            onKeyDown={aoTeclar}
            onChange={(e) => setEmail(e.target.value)}
          />
        </Campo>
      </div>
      {erros.telefone === undefined && erros.email === undefined && (
        <p className="nota">Basta um dos dois contatos, telefone ou e-mail.</p>
      )}
      {erroApi.geral && (
        <p className="erro-geral" role="alert">
          {erroApi.geral}
        </p>
      )}
    </>
  )

  if (compacto) {
    return (
      <div className="subformulario">
        <h3>Novo responsável</h3>
        {campos}
        <div className="subformulario-acoes">
          <button type="button" className="botao botao-texto" onClick={aoCancelar}>
            Cancelar
          </button>
          <button
            type="button"
            className="botao botao-secundario"
            disabled={salvando}
            onClick={() => void salvar()}
          >
            {salvando ? 'Salvando…' : 'Cadastrar e vincular'}
          </button>
        </div>
      </div>
    )
  }

  return (
    <form className="gaveta-formulario" noValidate onSubmit={aoEnviar}>
      <fieldset className="gaveta-conteudo" disabled={!podeEditar}>
        {campos}
      </fieldset>
      <footer className="gaveta-rodape">
        <span />
        <div className="gaveta-rodape-acoes">
          <button type="button" className="botao botao-texto" onClick={aoCancelar}>
            {podeEditar ? 'Cancelar' : 'Fechar'}
          </button>
          {podeEditar && (
            <button type="submit" className="botao botao-principal" disabled={salvando}>
              {salvando && 'Salvando…'}
              {!salvando && (responsavel ? 'Salvar alterações' : 'Cadastrar responsável')}
            </button>
          )}
        </div>
      </footer>
    </form>
  )
}   

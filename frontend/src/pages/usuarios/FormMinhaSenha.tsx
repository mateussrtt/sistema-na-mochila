import { useState, type FormEvent } from 'react'

import { SENHA_MINIMA } from '../../api/auth'
import { ApiError } from '../../api/client'
import { trocarMinhaSenha } from '../../api/usuarios'
import CampoSenha from '../../components/CampoSenha'

type Props = {
  aoSalvar: () => void
  aoCancelar: () => void
}

type Erros = Partial<Record<'atual' | 'nova' | 'confirmacao' | 'geral', string>>

export default function FormMinhaSenha({ aoSalvar, aoCancelar }: Props) {
  const [atual, setAtual] = useState('')
  const [nova, setNova] = useState('')
  const [confirmacao, setConfirmacao] = useState('')
  const [tentou, setTentou] = useState(false)
  const [salvando, setSalvando] = useState(false)
  const [erroApi, setErroApi] = useState<Erros>({})

  function validar(): Erros {
    const erros: Erros = {}
    if (!atual) erros.atual = 'Informe a senha que você usa hoje.'
    if (nova.length < SENHA_MINIMA) {
      erros.nova = `A nova senha precisa ter pelo menos ${SENHA_MINIMA} caracteres.`
    } else if (nova === atual) {
      erros.nova = 'A nova senha precisa ser diferente da atual.'
    }
    if (confirmacao !== nova) erros.confirmacao = 'As duas senhas não estão iguais.'
    return erros
  }

  const erros: Erros = tentou ? { ...validar(), ...erroApi } : {}

  async function aoEnviar(evento: FormEvent) {
    evento.preventDefault()
    setTentou(true)
    setErroApi({})
    if (Object.keys(validar()).length > 0) return

    setSalvando(true)
    try {
      await trocarMinhaSenha(atual, nova)
      aoSalvar()
    } catch (erro) {
      const api = erro instanceof ApiError ? erro : null
      if (api?.status === 422 && api.message === 'A senha atual não confere') {
        setErroApi({ atual: 'Esta não é a sua senha atual. Confira e tente de novo.' })
      } else {
        setErroApi({ geral: api?.message ?? 'Não foi possível trocar a senha. Tente de novo.' })
      }
    } finally {
      setSalvando(false)
    }
  }

  return (
    <form className="gaveta-formulario" noValidate onSubmit={(e) => void aoEnviar(e)}>
      <div className="gaveta-conteudo">
        <CampoSenha
          id="minha-senha-atual"
          rotulo="Senha atual"
          valor={atual}
          aoMudar={setAtual}
          erro={erros.atual}
          autoComplete="current-password"
          autoFocus
        />
        <CampoSenha
          id="minha-senha-nova"
          rotulo="Nova senha"
          valor={nova}
          aoMudar={setNova}
          erro={erros.nova}
          dica={`Pelo menos ${SENHA_MINIMA} caracteres. Uma frase curta é fácil de lembrar.`}
          autoComplete="new-password"
        />
        <CampoSenha
          id="minha-senha-confirmacao"
          rotulo="Repita a nova senha"
          valor={confirmacao}
          aoMudar={setConfirmacao}
          erro={erros.confirmacao}
          autoComplete="new-password"
        />
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
            {salvando ? 'Salvando…' : 'Trocar senha'}
          </button>
        </div>
      </footer>
    </form>
  )
}

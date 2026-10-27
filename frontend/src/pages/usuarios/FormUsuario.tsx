import { KeyRound, UserCheck, UserX } from 'lucide-react'
import { useState, type FormEvent } from 'react'

import {
  NOME_DO_PERFIL,
  O_QUE_O_PERFIL_FAZ,
  SENHA_MINIMA,
  type Perfil,
  type Usuario,
} from '../../api/auth'
import { ApiError } from '../../api/client'
import { cadastrarUsuario, editarUsuario, redefinirSenha } from '../../api/usuarios'
import Campo from '../../components/Campo'
import CampoSenha from '../../components/CampoSenha'
import { useSessao } from '../../sessao/contexto'
import { ligacaoDoCampo } from '../../utils/campo'
import { emailValido } from '../../utils/formato'

const PERFIS: Perfil[] = ['operador', 'consulta', 'administrador']

type Props = {
  usuario?: Usuario
  aoSalvar: (usuario: Usuario, mensagem: string) => void
  aoCancelar: () => void
}

type Erros = Partial<Record<'nome' | 'email' | 'senha' | 'novaSenha' | 'geral', string>>

export default function FormUsuario({ usuario, aoSalvar, aoCancelar }: Props) {
  const { usuario: logado } = useSessao()
  const ehVoce = usuario !== undefined && usuario.id === logado?.id

  const [nome, setNome] = useState(usuario?.nome ?? '')
  const [email, setEmail] = useState(usuario?.email ?? '')
  const [perfil, setPerfil] = useState<Perfil>(usuario?.perfil ?? 'operador')
  const [senha, setSenha] = useState('')
  const [tentou, setTentou] = useState(false)
  const [salvando, setSalvando] = useState(false)
  const [erroApi, setErroApi] = useState<Erros>({})

  // Nova senha definida pelo administrador, só na edição
  const [mudandoSenha, setMudandoSenha] = useState(false)
  const [novaSenha, setNovaSenha] = useState('')
  const [erroNovaSenha, setErroNovaSenha] = useState<string>()

  function validar(): Erros {
    const erros: Erros = {}
    if (nome.trim().length < 2) erros.nome = 'Informe o nome da pessoa.'
    if (!emailValido(email)) erros.email = 'Confira o e-mail, como nome@exemplo.com.'
    if (!usuario && senha.length < SENHA_MINIMA) {
      erros.senha = `A senha precisa ter pelo menos ${SENHA_MINIMA} caracteres.`
    }
    return erros
  }

  const erros: Erros = tentou ? { ...validar(), ...erroApi } : {}

  function tratarErro(erro: unknown) {
    const api = erro instanceof ApiError ? erro : null
    const campos = api?.campos ?? {}
    if (api?.status === 409) {
      setErroApi({ email: 'Já existe um usuário com este e-mail.' })
    } else if (campos.nome || campos.email || campos.senha) {
      setErroApi({ nome: campos.nome, email: campos.email, senha: campos.senha })
    } else {
      setErroApi({ geral: api?.message ?? 'Não foi possível salvar. Tente de novo.' })
    }
  }

  async function enviar(ativo: boolean, mensagem: string) {
    setTentou(true)
    setErroApi({})
    if (Object.keys(validar()).length > 0) return

    setSalvando(true)
    try {
      const salvo = usuario
        ? await editarUsuario(usuario.id, { nome, email, perfil, ativo })
        : await cadastrarUsuario({ nome, email, perfil, senha })
      aoSalvar(salvo, mensagem)
    } catch (erro) {
      tratarErro(erro)
    } finally {
      setSalvando(false)
    }
  }

  async function salvarNovaSenha() {
    if (!usuario) return
    if (novaSenha.length < SENHA_MINIMA) {
      setErroNovaSenha(`A senha precisa ter pelo menos ${SENHA_MINIMA} caracteres.`)
      return
    }
    setErroNovaSenha(undefined)
    setSalvando(true)
    try {
      const salvo = await redefinirSenha(usuario.id, novaSenha)
      aoSalvar(salvo, `Nova senha definida para ${salvo.nome}`)
    } catch (erro) {
      setErroNovaSenha(
        erro instanceof ApiError ? erro.message : 'Não foi possível salvar. Tente de novo.',
      )
    } finally {
      setSalvando(false)
    }
  }

  function aoEnviar(evento: FormEvent) {
    evento.preventDefault()
    void enviar(usuario?.ativo ?? true, usuario ? 'Alterações salvas' : 'Usuário cadastrado')
  }

  return (
    <form className="gaveta-formulario" noValidate onSubmit={aoEnviar}>
      <div className="gaveta-conteudo">
        <Campo id="usuario-nome" rotulo="Nome" erro={erros.nome}>
          <input
            {...ligacaoDoCampo('usuario-nome', erros.nome)}
            value={nome}
            autoComplete="off"
            onChange={(e) => setNome(e.target.value)}
          />
        </Campo>

        <Campo
          id="usuario-email"
          rotulo="E-mail"
          erro={erros.email}
          dica="É com ele que a pessoa entra no sistema."
        >
          <input
            {...ligacaoDoCampo('usuario-email', erros.email, 'dica')}
            type="email"
            inputMode="email"
            autoComplete="off"
            value={email}
            placeholder="nome@exemplo.com"
            onChange={(e) => setEmail(e.target.value)}
          />
        </Campo>

        <fieldset className="grupo perfis" disabled={ehVoce}>
          <legend>Perfil de acesso</legend>
          {PERFIS.map((p) => (
            <label key={p} className="perfil-opcao">
              <input
                type="radio"
                name="perfil"
                value={p}
                checked={perfil === p}
                onChange={() => setPerfil(p)}
              />
              <span className="perfil-texto">
                <strong>{NOME_DO_PERFIL[p]}</strong>
                <span>{O_QUE_O_PERFIL_FAZ[p]}</span>
              </span>
            </label>
          ))}
          {ehVoce && (
            <p className="campo-dica">
              Você não pode mudar o seu próprio perfil. Peça a outro administrador, se precisar.
            </p>
          )}
        </fieldset>

        {!usuario && (
          <CampoSenha
            id="usuario-senha"
            rotulo="Senha inicial"
            valor={senha}
            aoMudar={setSenha}
            erro={erros.senha}
            dica={`Pelo menos ${SENHA_MINIMA} caracteres. Passe para a pessoa, que pode trocá-la depois.`}
            autoComplete="new-password"
          />
        )}

        {usuario && !ehVoce && (
          <div className="grupo">
            <p className="grupo-titulo">Senha</p>
            {mudandoSenha ? (
              <div className="subformulario">
                <CampoSenha
                  id="usuario-nova-senha"
                  rotulo="Nova senha"
                  valor={novaSenha}
                  aoMudar={setNovaSenha}
                  erro={erroNovaSenha}
                  dica={`Pelo menos ${SENHA_MINIMA} caracteres. Passe a nova senha para ${usuario.nome.split(' ')[0]}.`}
                  autoComplete="new-password"
                  autoFocus
                />
                <div className="subformulario-acoes">
                  <button
                    type="button"
                    className="botao botao-texto"
                    onClick={() => {
                      setMudandoSenha(false)
                      setNovaSenha('')
                      setErroNovaSenha(undefined)
                    }}
                  >
                    Cancelar
                  </button>
                  <button
                    type="button"
                    className="botao botao-secundario"
                    disabled={salvando}
                    onClick={() => void salvarNovaSenha()}
                  >
                    Salvar nova senha
                  </button>
                </div>
              </div>
            ) : (
              <button
                type="button"
                className="botao botao-texto botao-com-icone"
                onClick={() => setMudandoSenha(true)}
              >
                <KeyRound size={18} aria-hidden="true" />
                Definir uma nova senha
              </button>
            )}
          </div>
        )}

        {erros.geral && (
          <p className="erro-geral" role="alert">
            {erros.geral}
          </p>
        )}
      </div>

      <footer className="gaveta-rodape">
        {usuario && !ehVoce ? (
          <button
            type="button"
            className="botao botao-texto botao-com-icone"
            disabled={salvando}
            onClick={() =>
              void enviar(!usuario.ativo, usuario.ativo ? 'Acesso desativado' : 'Acesso reativado')
            }
          >
            {usuario.ativo ? (
              <UserX size={18} aria-hidden="true" />
            ) : (
              <UserCheck size={18} aria-hidden="true" />
            )}
            {usuario.ativo ? 'Desativar acesso' : 'Reativar acesso'}
          </button>
        ) : (
          <span />
        )}
        <div className="gaveta-rodape-acoes">
          <button type="button" className="botao botao-texto" onClick={aoCancelar}>
            Cancelar
          </button>
          <button type="submit" className="botao botao-principal" disabled={salvando}>
            {salvando ? 'Salvando…' : usuario ? 'Salvar alterações' : 'Cadastrar usuário'}
          </button>
        </div>
      </footer>
    </form>
  )
}

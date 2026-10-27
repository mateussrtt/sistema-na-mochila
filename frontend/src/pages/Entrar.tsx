import { Eye, EyeOff } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router'

import { ApiError } from '../api/client'
import Campo from '../components/Campo'
import { useSessao } from '../sessao/contexto'
import { ligacaoDoCampo } from '../utils/campo'

type Erros = Partial<Record<'email' | 'senha' | 'geral', string>>

export default function Entrar() {
  const { usuario, entrar } = useSessao()
  const navegar = useNavigate()
  const local = useLocation()
  const voltarPara = (local.state as { voltarPara?: string } | null)?.voltarPara ?? '/'

  const [email, setEmail] = useState('')
  const [senha, setSenha] = useState('')
  const [mostrarSenha, setMostrarSenha] = useState(false)
  const [erros, setErros] = useState<Erros>({})
  const [entrando, setEntrando] = useState(false)

  if (usuario) return <Navigate to={voltarPara} replace />

  async function aoEnviar(evento: FormEvent) {
    evento.preventDefault()
    const novos: Erros = {}
    if (!email.trim()) novos.email = 'Informe seu e-mail.'
    if (!senha) novos.senha = 'Informe sua senha.'
    setErros(novos)
    if (Object.keys(novos).length > 0) return

    setEntrando(true)
    try {
      await entrar(email, senha)
      navegar(voltarPara, { replace: true })
    } catch (erro) {
      setErros({
        geral:
          erro instanceof ApiError && erro.status === 401
            ? 'E-mail ou senha incorretos. Confira e tente de novo.'
            : 'Não foi possível entrar agora. Confira sua conexão e tente de novo.',
      })
    } finally {
      setEntrando(false)
    }
  }

  return (
    <div className="entrar">
      <aside className="entrar-marca">
        <span className="marca-selo marca-selo-grande" aria-hidden="true">
          NM
        </span>
        <div>
          <p className="entrar-nome">Na Mochila</p>
          <p className="entrar-subtitulo">Gestão financeira da associação</p>
        </div>
        <p className="entrar-rodape">Robótica educacional no Médio Piracicaba</p>
      </aside>

      <main className="entrar-area">
        <form className="entrar-formulario" noValidate onSubmit={(e) => void aoEnviar(e)}>
          <header>
            <h1>Entrar</h1>
            <p>Use o e-mail e a senha cadastrados pela coordenação.</p>
          </header>

          <Campo id="entrar-email" rotulo="E-mail" erro={erros.email}>
            <input
              {...ligacaoDoCampo('entrar-email', erros.email)}
              type="email"
              inputMode="email"
              autoComplete="username"
              autoFocus
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </Campo>

          <Campo id="entrar-senha" rotulo="Senha" erro={erros.senha}>
            <div className="campo-senha">
              <input
                {...ligacaoDoCampo('entrar-senha', erros.senha)}
                type={mostrarSenha ? 'text' : 'password'}
                autoComplete="current-password"
                value={senha}
                onChange={(e) => setSenha(e.target.value)}
              />
              <button
                type="button"
                className="botao-icone"
                aria-label={mostrarSenha ? 'Esconder senha' : 'Mostrar senha'}
                aria-pressed={mostrarSenha}
                onClick={() => setMostrarSenha((m) => !m)}
              >
                {mostrarSenha ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </Campo>

          {erros.geral && (
            <p className="erro-geral" role="alert">
              {erros.geral}
            </p>
          )}

          <button type="submit" className="botao botao-principal" disabled={entrando}>
            {entrando ? 'Entrando…' : 'Entrar'}
          </button>
        </form>
      </main>
    </div>
  )
}

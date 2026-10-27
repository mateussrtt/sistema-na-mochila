import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'

import { buscarUsuarioLogado, entrar as pedirLogin, type Usuario } from '../api/auth'
import { ContextoDaSessao, type Sessao } from './contexto'
import { apagarToken, lerToken, salvarToken, SESSAO_EXPIROU } from './token'

/** Guarda quem está logado e deixa essa informação disponível para todas as telas. */
export default function ProvedorDeSessao({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(null)
  const [conferindo, setConferindo] = useState(() => lerToken() !== null)

  // Ao abrir o site, confere se o token guardado ainda vale
  useEffect(() => {
    if (!lerToken()) return
    const controle = new AbortController()
    buscarUsuarioLogado(controle.signal)
      .then(setUsuario)
      .catch(() => {
        if (!controle.signal.aborted) apagarToken()
      })
      .finally(() => {
        if (!controle.signal.aborted) setConferindo(false)
      })
    return () => controle.abort()
  }, [])

  // Se a API recusar o token no meio do uso, volta para a tela de login
  useEffect(() => {
    const aoExpirar = () => setUsuario(null)
    window.addEventListener(SESSAO_EXPIROU, aoExpirar)
    return () => window.removeEventListener(SESSAO_EXPIROU, aoExpirar)
  }, [])

  const entrar = useCallback(async (email: string, senha: string) => {
    const resposta = await pedirLogin(email, senha)
    salvarToken(resposta.token)
    setUsuario(resposta.usuario)
  }, [])

  const sair = useCallback(() => {
    apagarToken()
    setUsuario(null)
  }, [])

  const sessao = useMemo<Sessao>(
    () => ({
      usuario,
      conferindo,
      podeEditar: usuario?.perfil === 'administrador' || usuario?.perfil === 'operador',
      ehAdmin: usuario?.perfil === 'administrador',
      entrar,
      sair,
      atualizarUsuario: setUsuario,
    }),
    [usuario, conferindo, entrar, sair],
  )

  return <ContextoDaSessao.Provider value={sessao}>{children}</ContextoDaSessao.Provider>
}

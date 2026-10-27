import { createContext, useContext } from 'react'

import type { Usuario } from '../api/auth'

export type Sessao = {
  /** Quem está logado, ou null se ninguém entrou */
  usuario: Usuario | null
  /** true enquanto confere, ao abrir o site, se o token guardado ainda vale */
  conferindo: boolean
  /** Administrador e operador podem cadastrar e editar. Consulta só visualiza. */
  podeEditar: boolean
  /** Só o administrador gerencia usuários */
  ehAdmin: boolean
  entrar: (email: string, senha: string) => Promise<void>
  sair: () => void
  /** Atualiza nome e e-mail no menu depois que a pessoa edita o próprio cadastro */
  atualizarUsuario: (usuario: Usuario) => void
}

export const ContextoDaSessao = createContext<Sessao | null>(null)

export function useSessao(): Sessao {
  const sessao = useContext(ContextoDaSessao)
  if (!sessao) throw new Error('useSessao precisa estar dentro de <ProvedorDeSessao>')
  return sessao
}

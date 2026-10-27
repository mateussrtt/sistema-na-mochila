import { apiEnviar, apiGet } from './client'

export type Perfil = 'administrador' | 'operador' | 'consulta'

export type Usuario = {
  id: number
  nome: string
  email: string
  perfil: Perfil
  ativo: boolean
}

export const NOME_DO_PERFIL: Record<Perfil, string> = {
  administrador: 'Administrador',
  operador: 'Operador financeiro',
  consulta: 'Consulta',
}

export const O_QUE_O_PERFIL_FAZ: Record<Perfil, string> = {
  administrador: 'Faz tudo, inclusive cadastrar usuários e cancelar lançamentos.',
  operador: 'Cadastra alunos e matrículas e lança pagamentos, despesas e receitas.',
  consulta: 'Só visualiza cadastros e relatórios, sem alterar nada.',
}

export const SENHA_MINIMA = 8

export function entrar(email: string, senha: string) {
  return apiEnviar<{ token: string; usuario: Usuario }>('POST', '/api/auth/login', {
    email,
    senha,
  })
}

export function buscarUsuarioLogado(signal?: AbortSignal) {
  return apiGet<Usuario>('/api/auth/eu', signal)
}

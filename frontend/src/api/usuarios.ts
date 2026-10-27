import type { Perfil, Usuario } from './auth'
import { apiEnviar, apiGet } from './client'

export type UsuarioEntrada = {
  nome: string
  email: string
  perfil: Perfil
}

export function listarUsuarios(signal?: AbortSignal) {
  return apiGet<Usuario[]>('/api/usuarios', signal)
}

export function cadastrarUsuario(dados: UsuarioEntrada & { senha: string }) {
  return apiEnviar<Usuario>('POST', '/api/usuarios', dados)
}

export function editarUsuario(id: number, dados: UsuarioEntrada & { ativo: boolean }) {
  return apiEnviar<Usuario>('PUT', `/api/usuarios/${id}`, dados)
}

/** O administrador define uma nova senha para outra pessoa */
export function redefinirSenha(id: number, senha: string) {
  return apiEnviar<Usuario>('PATCH', `/api/usuarios/${id}/senha`, { senha })
}

/** Qualquer perfil troca a própria senha */
export function trocarMinhaSenha(senhaAtual: string, novaSenha: string) {
  return apiEnviar<Usuario>('PATCH', '/api/auth/senha', {
    senha_atual: senhaAtual,
    nova_senha: novaSenha,
  })
}

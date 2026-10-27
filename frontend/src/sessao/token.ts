// Guarda o token de login no navegador, para a sessão continuar depois de recarregar a página.

const CHAVE = 'na-mochila:token'

/** Avisado quando a API recusa o token (sessão vencida ou usuário desativado) */
export const SESSAO_EXPIROU = 'na-mochila:sessao-expirou'

export function lerToken(): string | null {
  try {
    return localStorage.getItem(CHAVE)
  } catch {
    return null
  }
}

export function salvarToken(token: string) {
  try {
    localStorage.setItem(CHAVE, token)
  } catch {
    // Sem acesso ao armazenamento: a sessão dura até fechar a aba
  }
}

export function apagarToken() {
  try {
    localStorage.removeItem(CHAVE)
  } catch {
    // nada a apagar
  }
}

// Cliente único para falar com a API. Todas as telas devem usar estas funções.

export const API_URL = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/$/, '')

export class ApiError extends Error {
  readonly status: number
  /** Mensagens de validação da API, por nome do campo */
  readonly campos: Record<string, string>

  constructor(status: number, message: string, campos: Record<string, string> = {}) {
    super(message)
    this.status = status
    this.campos = campos
  }
}

type ErroDeCampo = { loc: (string | number)[]; msg: string }

async function lerErro(resposta: Response): Promise<ApiError> {
  let mensagem = `A API respondeu com erro ${resposta.status}.`
  const campos: Record<string, string> = {}
  try {
    const corpo = (await resposta.json()) as { detail?: string | ErroDeCampo[] }
    if (typeof corpo.detail === 'string') {
      mensagem = corpo.detail
    } else if (Array.isArray(corpo.detail)) {
      for (const erro of corpo.detail) {
        campos[String(erro.loc.at(-1))] = erro.msg.replace(/^Value error, /, '')
      }
      mensagem = Object.values(campos)[0] ?? mensagem
    }
  } catch {
    // resposta sem JSON: fica a mensagem genérica
  }
  return new ApiError(resposta.status, mensagem, campos)
}

async function requisitar<T>(path: string, init?: RequestInit): Promise<T> {
  const resposta = await fetch(`${API_URL}${path}`, init)
  if (!resposta.ok) {
    throw await lerErro(resposta)
  }
  return (await resposta.json()) as T
}

export function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  return requisitar<T>(path, { signal })
}

export function apiEnviar<T>(metodo: 'POST' | 'PUT', path: string, corpo: unknown): Promise<T> {
  return requisitar<T>(path, {
    method: metodo,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(corpo),
  })
}

export type Health = {
  status: string
  banco: string
}

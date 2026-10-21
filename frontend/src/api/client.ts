// Cliente único para falar com a API. Todas as telas devem usar estas funções.

export const API_URL = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/$/, '')

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  const resposta = await fetch(`${API_URL}${path}`, { signal })
  if (!resposta.ok) {
    throw new ApiError(resposta.status, `Erro ${resposta.status} ao chamar ${path}`)
  }
  return (await resposta.json()) as T
}

export type Health = {
  status: string
  banco: string
}

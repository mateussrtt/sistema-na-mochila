import type { Situacao } from './cadastros'
import { apiEnviar, apiGet } from './client'

/** Empresa que paga as mensalidades de alunos apadrinhados */
export type Padrinho = {
  id: number
  nome: string
  /** Os 14 caracteres, sem máscara */
  cnpj: string | null
  /** Pessoa da empresa que combina e recebe a cobrança */
  contato: string | null
  /** Obrigatório: é por ele que se fala com a empresa */
  telefone: string
  /** Obrigatório */
  email: string
  /** Dia do mês em que a cobrança vence, de 1 a 28 */
  dia_vencimento: number
  /** Dia até o qual a nota deve ser emitida, se houver */
  emitir_ate_dia: number | null
  ativo: boolean
}

export type PadrinhoEntrada = {
  nome: string
  cnpj: string
  contato: string
  telefone: string
  email: string
  dia_vencimento: number
  emitir_ate_dia: number | null
  ativo: boolean
}

export function listarPadrinhos(busca: string, situacao: Situacao, signal?: AbortSignal) {
  const parametros = new URLSearchParams({ busca, situacao })
  return apiGet<Padrinho[]>(`/api/padrinhos?${parametros}`, signal)
}

export function salvarPadrinho(dados: PadrinhoEntrada, id?: number) {
  return id === undefined
    ? apiEnviar<Padrinho>('POST', '/api/padrinhos', dados)
    : apiEnviar<Padrinho>('PUT', `/api/padrinhos/${id}`, dados)
}

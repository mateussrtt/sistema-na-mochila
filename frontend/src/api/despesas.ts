import type { Situacao } from './cadastros'
import { apiEnviar, apiGet } from './client'

/** Para onde o dinheiro vai: kits, viagens, custos fixos... */
export type CategoriaDespesa = {
  id: number
  nome: string
  ativo: boolean
}

export type CategoriaDespesaEntrada = {
  nome: string
  ativo: boolean
}

export type Despesa = {
  id: number
  /** Dia em que o dinheiro saiu (AAAA-MM-DD) */
  data_despesa: string
  /** Vem como texto ("89.90") para não perder as casas decimais */
  valor: string
  categoria: CategoriaDespesa
  descricao: string
  /** Para quem foi pago */
  favorecido: string
  /** Nome de quem registrou */
  registrado_por: string
  /** Data e hora do registro, em ISO 8601 */
  registrado_em: string
}

export type NovaDespesa = {
  data_despesa: string
  valor: string
  categoria_id: number
  descricao: string
  favorecido: string
}

/** `mes` no formato AAAA-MM; vazio traz todos os meses. `categoriaId` nulo traz todas. */
export function listarDespesas(
  mes: string,
  categoriaId: number | null,
  busca: string,
  signal?: AbortSignal,
) {
  const parametros = new URLSearchParams({ mes, busca })
  if (categoriaId !== null) parametros.set('categoria_id', String(categoriaId))
  return apiGet<Despesa[]>(`/api/despesas?${parametros}`, signal)
}

export function registrarDespesa(dados: NovaDespesa) {
  return apiEnviar<Despesa>('POST', '/api/despesas', dados)
}

export function listarCategoriasDespesa(situacao: Situacao, signal?: AbortSignal) {
  const parametros = new URLSearchParams({ situacao })
  return apiGet<CategoriaDespesa[]>(`/api/categorias-despesa?${parametros}`, signal)
}

export function salvarCategoriaDespesa(dados: CategoriaDespesaEntrada, id?: number) {
  return id === undefined
    ? apiEnviar<CategoriaDespesa>('POST', '/api/categorias-despesa', dados)
    : apiEnviar<CategoriaDespesa>('PUT', `/api/categorias-despesa/${id}`, dados)
}

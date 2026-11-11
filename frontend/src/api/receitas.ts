import type { Situacao } from './cadastros'
import type { Cancelamento } from './cancelamento'
import { apiEnviar, apiGet } from './client'

/** De onde o dinheiro vem: patrocínio, projetos e editais, doações... */
export type CategoriaReceita = {
  id: number
  nome: string
  ativo: boolean
}

export type CategoriaReceitaEntrada = {
  nome: string
  ativo: boolean
}

export type Receita = {
  id: number
  /** Dia em que o dinheiro entrou (AAAA-MM-DD) */
  data_receita: string
  /** Vem como texto ("89.90") para não perder as casas decimais */
  valor: string
  categoria: CategoriaReceita
  /** Quem pagou: o patrocinador, o edital, quem doou */
  origem: string
  /** Detalhe opcional */
  descricao: string | null
  /** Nome de quem registrou */
  registrado_por: string
  /** Data e hora do registro, em ISO 8601 */
  registrado_em: string
  /** Lançamento cancelado continua na lista, com o motivo, mas não entra nos totais */
  cancelamento: Cancelamento | null
  /** Esta receita é a correção de outra, que foi cancelada */
  substitui_id: number | null
  /** Esta receita foi cancelada e corrigida por outra */
  substituida_por_id: number | null
}

export type NovaReceita = {
  data_receita: string
  valor: string
  categoria_id: number
  origem: string
  descricao: string | null
}

/** `mes` no formato AAAA-MM; vazio traz todos os meses. `categoriaId` nulo traz todas. */
export function listarReceitas(
  mes: string,
  categoriaId: number | null,
  busca: string,
  signal?: AbortSignal,
) {
  const parametros = new URLSearchParams({ mes, busca })
  if (categoriaId !== null) parametros.set('categoria_id', String(categoriaId))
  return apiGet<Receita[]>(`/api/receitas?${parametros}`, signal)
}

export function registrarReceita(dados: NovaReceita) {
  return apiEnviar<Receita>('POST', '/api/receitas', dados)
}

/** Só o administrador. A receita continua na lista, marcada como cancelada (RF17, RN12). */
export function cancelarReceita(id: number, motivo: string) {
  return apiEnviar<Receita>('PATCH', `/api/receitas/${id}/cancelar`, { motivo })
}

/**
 * Só o administrador. Cancela a receita errada com o motivo e registra a certa no lugar, tudo
 * de uma vez. Devolve a receita nova.
 */
export function corrigirReceita(id: number, dados: NovaReceita & { motivo: string }) {
  return apiEnviar<Receita>('POST', `/api/receitas/${id}/corrigir`, dados)
}

export function listarCategoriasReceita(situacao: Situacao, signal?: AbortSignal) {
  const parametros = new URLSearchParams({ situacao })
  return apiGet<CategoriaReceita[]>(`/api/categorias-receita?${parametros}`, signal)
}

export function salvarCategoriaReceita(dados: CategoriaReceitaEntrada, id?: number) {
  return id === undefined
    ? apiEnviar<CategoriaReceita>('POST', '/api/categorias-receita', dados)
    : apiEnviar<CategoriaReceita>('PUT', `/api/categorias-receita/${id}`, dados)
}

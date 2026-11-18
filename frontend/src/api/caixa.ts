import { apiGet } from './client'

/** Quanto entrou ou saiu e em quantos lançamentos */
export type Parcela = {
  /** Vem como texto ("150.00") para não perder as casas decimais */
  total: string
  quantidade: number
}

export type OrigemDaEntrada = Parcela & {
  origem: 'mensalidades' | 'apadrinhamento' | 'receitas'
  /** Nome para mostrar na tela */
  rotulo: string
}

/** Uma linha do fluxo de caixa: mensalidades, apadrinhamento ou uma categoria (RF20) */
export type LinhaDoFluxo = Parcela & {
  origem: 'mensalidades' | 'apadrinhamento' | 'receita' | 'despesa'
  /** Só as linhas de receita e de despesa têm categoria */
  categoria_id: number | null
  nome: string
}

/** O caixa de um mês: o que entrou, o que saiu, o saldo (RF19) e o fluxo por categoria (RF20) */
export type Caixa = {
  /** AAAA-MM */
  mes: string
  entradas: Parcela
  /** Sempre as três origens, na mesma ordem */
  origens_das_entradas: OrigemDaEntrada[]
  saidas: Parcela
  /** Pode ser negativo */
  saldo: string
  /** Só as linhas com movimento no mês, do maior valor para o menor */
  entradas_por_categoria: LinhaDoFluxo[]
  saidas_por_categoria: LinhaDoFluxo[]
}

/** `mes` no formato AAAA-MM, do mês atual para trás */
export function consultarCaixa(mes: string, signal?: AbortSignal) {
  const parametros = new URLSearchParams({ mes })
  return apiGet<Caixa>(`/api/caixa?${parametros}`, signal)
}

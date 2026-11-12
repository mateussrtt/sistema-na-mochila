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

/** O caixa de um mês: o que entrou, o que saiu e o saldo (RF19) */
export type Caixa = {
  /** AAAA-MM */
  mes: string
  entradas: Parcela
  /** Sempre as três origens, na mesma ordem */
  origens_das_entradas: OrigemDaEntrada[]
  saidas: Parcela
  /** Pode ser negativo */
  saldo: string
}

/** `mes` no formato AAAA-MM, do mês atual para trás */
export function consultarCaixa(mes: string, signal?: AbortSignal) {
  const parametros = new URLSearchParams({ mes })
  return apiGet<Caixa>(`/api/caixa?${parametros}`, signal)
}

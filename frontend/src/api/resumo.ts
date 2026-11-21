import { apiGet } from './client'

/** Quanto entrou ou saiu no mês e em quantos lançamentos */
export type TotalDoMes = {
  /** Vem como texto ("150.00") para não perder as casas decimais */
  total: string
  quantidade: number
}

/** As mensalidades em atraso de todos os meses, como no painel de pendências */
export type EmAtraso = {
  total: string
  mensalidades: number
  alunos: number
  responsaveis: number
}

/**
 * O resumo do mês atual para a tela inicial (RF23). São os mesmos números do caixa
 * (recebido, despesas e saldo) e do painel de pendências (em atraso).
 */
export type ResumoDoMes = {
  /** AAAA-MM */
  mes: string
  recebido: TotalDoMes
  em_atraso: EmAtraso
  despesas: TotalDoMes
  /** Pode ser negativo */
  saldo: string
}

export function consultarResumo(signal?: AbortSignal) {
  return apiGet<ResumoDoMes>('/api/resumo', signal)
}

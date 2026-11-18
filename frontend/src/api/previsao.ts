import { apiGet } from './client'

/** A previsão de um mês: a soma das mensalidades das matrículas em vigor nele (RN11) */
export type MesPrevisto = {
  /** O dia 1 do mês: 2026-11-01 */
  mes: string
  /** Vem como texto ("150.00") para não perder as casas decimais */
  previsto: string
  /** Quantos alunos pagam mensalidade no mês */
  alunos: number
}

/** O mês atual, com o que da previsão já entrou e o que falta (RF21) */
export type MesAtual = MesPrevisto & {
  recebido: string
  /** Mensalidades isentas ou canceladas: estavam previstas, mas não vão entrar */
  dispensado: string
  falta: string
}

/** Previsão do mês atual e dos 11 seguintes (RF21, RF22). Só mensalidades (RN11). */
export type Previsao = {
  atual: MesAtual
  meses: MesPrevisto[]
  total: string
}

export function consultarPrevisao(signal?: AbortSignal) {
  return apiGet<Previsao>('/api/previsao', signal)
}

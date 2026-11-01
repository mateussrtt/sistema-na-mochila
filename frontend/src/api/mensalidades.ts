import type { AlunoResumo, Bolsa } from './cadastros'
import { apiEnviar, apiGet } from './client'

export type SituacaoMensalidade = 'a_vencer' | 'atrasada' | 'paga' | 'isenta' | 'cancelada'

export const NOME_DA_SITUACAO: Record<SituacaoMensalidade, string> = {
  a_vencer: 'A vencer',
  atrasada: 'Atrasada',
  paga: 'Paga',
  isenta: 'Isenta',
  cancelada: 'Cancelada',
}

export type Mensalidade = {
  id: number
  matricula_id: number
  aluno: AlunoResumo
  bolsa: Bolsa
  /** Sempre o dia 1 do mês de referência (AAAA-MM-01) */
  competencia: string
  /** Vem como texto ("150.00") para não perder as casas decimais */
  valor: string
  data_vencimento: string
  status: 'pendente' | 'paga' | 'isenta' | 'cancelada'
  /** Calculada pela API: a vencer só vira atrasada a partir do dia seguinte ao vencimento */
  situacao: SituacaoMensalidade
  dias_em_atraso: number
}

export type ResultadoDaGeracao = {
  competencia: string
  geradas: number
  ja_existiam: number
  bolsa_integral: number
  ainda_nao_comecaram: number
}

/** `mes` no formato AAAA-MM. O filtro por situação é feito na tela, com a lista do mês. */
export function listarMensalidades(mes: string, busca: string, signal?: AbortSignal) {
  const parametros = new URLSearchParams({ mes, busca })
  return apiGet<Mensalidade[]>(`/api/mensalidades?${parametros}`, signal)
}

export function gerarMensalidades(mes: string) {
  return apiEnviar<ResultadoDaGeracao>('POST', '/api/mensalidades/gerar', { competencia: mes })
}

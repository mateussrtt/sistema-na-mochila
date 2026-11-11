import type { AlunoResumo, Bolsa } from './cadastros'
import type { Cancelamento } from './cancelamento'
import { apiEnviar, apiGet } from './client'

export type SituacaoMensalidade = 'a_vencer' | 'atrasada' | 'paga' | 'isenta' | 'cancelada'

export const NOME_DA_SITUACAO: Record<SituacaoMensalidade, string> = {
  a_vencer: 'A vencer',
  atrasada: 'Atrasada',
  paga: 'Paga',
  isenta: 'Isenta',
  cancelada: 'Cancelada',
}

export type FormaDePagamento = 'pix' | 'dinheiro' | 'boleto' | 'outra'

export const NOME_DA_FORMA: Record<FormaDePagamento, string> = {
  pix: 'PIX',
  dinheiro: 'Dinheiro',
  boleto: 'Boleto',
  outra: 'Outra',
}

export type Pagamento = {
  data_pagamento: string
  /** Vem como texto ("150.00") para não perder as casas decimais */
  valor_pago: string
  forma_pagamento: FormaDePagamento
  observacao: string | null
  registrado_por: string
  /** Data e hora do registro, em ISO 8601 */
  registrado_em: string
}

/** Pagamento registrado errado e cancelado: continua no histórico, com o motivo (RF17) */
export type PagamentoCancelado = Pagamento & { cancelamento: Cancelamento }

export type NovoPagamento = {
  data_pagamento: string
  valor_pago: string
  forma_pagamento: FormaDePagamento
  observacao: string
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
  /** Só a mensalidade paga tem pagamento */
  pagamento: Pagamento | null
  /** Pagamentos cancelados, do mais recente para o mais antigo */
  pagamentos_cancelados: PagamentoCancelado[]
  /** Só a mensalidade isenta ou cancelada tem motivo, quem alterou e quando (ISO 8601) */
  motivo: string | null
  alterado_por: string | null
  alterado_em: string | null
}

export type ResultadoDaGeracao = {
  competencia: string
  geradas: number
  ja_existiam: number
  bolsa_integral: number
  /** Apadrinhados: quem cobra é a empresa, não o responsável */
  apadrinhados: number
  /** Quantos apadrinhados entraram agora na cobrança da empresa */
  apadrinhados_incluidos: number
  /** Quantas cobranças de empresa nasceram nesta geração */
  cobrancas_criadas: number
  ainda_nao_comecaram: number
}

/** `mes` no formato AAAA-MM. O filtro por situação é feito na tela, com a lista do mês. */
export function listarMensalidades(mes: string, busca: string, signal?: AbortSignal) {
  const parametros = new URLSearchParams({ mes, busca })
  return apiGet<Mensalidade[]>(`/api/mensalidades?${parametros}`, signal)
}

export function registrarPagamento(id: number, pagamento: NovoPagamento) {
  return apiEnviar<Mensalidade>('POST', `/api/mensalidades/${id}/pagamento`, pagamento)
}

/**
 * Só o administrador. Cancela o pagamento registrado errado: a mensalidade volta a ficar
 * pendente e o pagamento continua no histórico, com o motivo (RF17, RN12).
 */
export function cancelarPagamento(id: number, motivo: string) {
  return apiEnviar<Mensalidade>('PATCH', `/api/mensalidades/${id}/pagamento/cancelar`, { motivo })
}

/** Só o administrador. Só uma mensalidade pendente pode ser isentada (RF14, RN13). */
export function isentarMensalidade(id: number, motivo: string) {
  return apiEnviar<Mensalidade>('PATCH', `/api/mensalidades/${id}/isentar`, { motivo })
}

/** Só o administrador. A mensalidade continua na lista, com o motivo (RN12). */
export function cancelarMensalidade(id: number, motivo: string) {
  return apiEnviar<Mensalidade>('PATCH', `/api/mensalidades/${id}/cancelar`, { motivo })
}

export function gerarMensalidades(mes: string) {
  return apiEnviar<ResultadoDaGeracao>('POST', '/api/mensalidades/gerar', { competencia: mes })
}

import type { AlunoResumo } from './cadastros'
import { apiEnviar, apiGet } from './client'

export type StatusCobranca = 'a_emitir' | 'emitida' | 'paga' | 'cancelada'

export type SituacaoCobranca = 'a_emitir' | 'a_vencer' | 'atrasada' | 'paga' | 'cancelada'

export const NOME_DA_SITUACAO_COBRANCA: Record<SituacaoCobranca, string> = {
  a_emitir: 'A emitir',
  a_vencer: 'A vencer',
  atrasada: 'Atrasada',
  paga: 'Paga',
  cancelada: 'Cancelada',
}

export type FormaDePagamentoCobranca = 'pix' | 'transferencia' | 'boleto' | 'outra'

export const NOME_DA_FORMA_COBRANCA: Record<FormaDePagamentoCobranca, string> = {
  pix: 'PIX',
  transferencia: 'Transferência',
  boleto: 'Boleto',
  outra: 'Outra',
}

export type ItemDaCobranca = {
  mensalidade_id: number
  matricula_id: number
  aluno: AlunoResumo
  /** Vem como texto ("150.00") para não perder as casas decimais */
  valor: string
}

export type Nota = {
  numero_nota: string
  data_emissao: string
  registrada_por: string
  /** Data e hora do registro, em ISO 8601 */
  registrada_em: string
}

export type PagamentoDaCobranca = {
  data_pagamento: string
  valor_pago: string
  forma_pagamento: FormaDePagamentoCobranca
  observacao: string | null
  registrado_por: string
  registrado_em: string
}

export type Cobranca = {
  id: number
  padrinho: { id: number; nome: string; ativo: boolean }
  /** Sempre o dia 1 do mês de referência (AAAA-MM-01) */
  competencia: string
  /** Soma das mensalidades dos alunos, como texto ("450.00") */
  valor: string
  status: StatusCobranca
  /** Calculada pela API: a vencer só vira atrasada a partir do dia seguinte ao vencimento */
  situacao: SituacaoCobranca
  /** A nota ainda não foi emitida e o prazo combinado com a empresa passou */
  emissao_atrasada: boolean
  limite_emissao: string | null
  data_vencimento: string
  dias_em_atraso: number
  alunos: ItemDaCobranca[]
  gerada_por: string
  gerada_em: string
  nota: Nota | null
  pagamento: PagamentoDaCobranca | null
  motivo: string | null
  cancelada_por: string | null
  cancelada_em: string | null
}

export type NovaNota = {
  numero_nota: string
  data_emissao: string
  data_vencimento: string
}

export type NovoPagamentoDaCobranca = {
  data_pagamento: string
  valor_pago: string
  forma_pagamento: FormaDePagamentoCobranca
  observacao: string
}

/** `mes` no formato AAAA-MM; vazio traz todos os meses. O filtro de situação é feito na tela. */
export function listarCobrancas(mes: string, padrinhoId: number | null, signal?: AbortSignal) {
  const parametros = new URLSearchParams({ mes })
  if (padrinhoId !== null) parametros.set('padrinho_id', String(padrinhoId))
  return apiGet<Cobranca[]>(`/api/cobrancas?${parametros}`, signal)
}

/** Registra a nota emitida (ou corrige, enquanto a cobrança não foi paga) */
export function registrarNota(id: number, nota: NovaNota) {
  return apiEnviar<Cobranca>('PATCH', `/api/cobrancas/${id}/nota`, nota)
}

export function registrarPagamentoDaCobranca(id: number, pagamento: NovoPagamentoDaCobranca) {
  return apiEnviar<Cobranca>('POST', `/api/cobrancas/${id}/pagamento`, pagamento)
}

/** Só o administrador (RN13). A cobrança continua na lista, com o motivo (RN12). */
export function cancelarCobranca(id: number, motivo: string) {
  return apiEnviar<Cobranca>('PATCH', `/api/cobrancas/${id}/cancelar`, { motivo })
}

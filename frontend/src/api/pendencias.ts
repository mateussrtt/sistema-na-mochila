import { apiGet } from './client'

export type MensalidadeEmAtraso = {
  id: number
  /** Sempre o dia 1 do mês de referência (AAAA-MM-01) */
  competencia: string
  /** Vem como texto ("150.00") para não perder as casas decimais */
  valor: string
  data_vencimento: string
  dias_em_atraso: number
}

export type AlunoEmAtraso = {
  id: number
  nome: string
  ativo: boolean
  total: string
  mensalidades: MensalidadeEmAtraso[]
}

export type ContatoDoResponsavel = {
  id: number
  nome: string
  telefone: string | null
  email: string | null
}

/**
 * Os alunos que têm exatamente os mesmos responsáveis, numa pendência só. Cada aluno em atraso
 * aparece em um único grupo: a soma dos totais dos grupos é o total em aberto do resumo.
 */
export type GrupoEmAtraso = {
  responsaveis: ContatoDoResponsavel[]
  alunos: AlunoEmAtraso[]
  total: string
  maior_atraso: number
}

export type Pendencias = {
  mes: string | null
  resumo: {
    responsaveis: number
    alunos: number
    mensalidades: number
    total_em_aberto: string
  }
  grupos: GrupoEmAtraso[]
}

/** `mes` no formato AAAA-MM. Sem ele, traz as mensalidades em atraso de todos os meses. */
export function listarPendencias(mes: string | null, signal?: AbortSignal) {
  const consulta = mes ? `?${new URLSearchParams({ mes })}` : ''
  return apiGet<Pendencias>(`/api/pendencias${consulta}`, signal)
}

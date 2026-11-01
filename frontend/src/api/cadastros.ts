import { apiEnviar, apiGet } from './client'

export type Responsavel = {
  id: number
  nome: string
  telefone: string | null
  email: string | null
}

export type ResponsavelEntrada = {
  nome: string
  telefone: string
  email: string
}

export type Aluno = {
  id: number
  nome: string
  data_nascimento: string | null
  escola: string | null
  municipio: string | null
  ativo: boolean
  responsaveis: Responsavel[]
}

export type AlunoEntrada = {
  nome: string
  data_nascimento: string
  escola: string
  municipio: string
  responsavel_ids: number[]
  ativo: boolean
}

export type Situacao = 'ativos' | 'inativos' | 'todos'

export function listarAlunos(busca: string, situacao: Situacao, signal?: AbortSignal) {
  const parametros = new URLSearchParams({ busca, situacao })
  return apiGet<Aluno[]>(`/api/alunos?${parametros}`, signal)
}

export function salvarAluno(dados: AlunoEntrada, id?: number) {
  return id === undefined
    ? apiEnviar<Aluno>('POST', '/api/alunos', dados)
    : apiEnviar<Aluno>('PUT', `/api/alunos/${id}`, dados)
}

export function listarResponsaveis(busca: string, signal?: AbortSignal) {
  return apiGet<Responsavel[]>(`/api/responsaveis?${new URLSearchParams({ busca })}`, signal)
}

export function salvarResponsavel(dados: ResponsavelEntrada, id?: number) {
  return id === undefined
    ? apiEnviar<Responsavel>('POST', '/api/responsaveis', dados)
    : apiEnviar<Responsavel>('PUT', `/api/responsaveis/${id}`, dados)
}

export type AlunoResumo = {
  id: number
  nome: string
  ativo: boolean
}

/**
 * Com bolsa integral o aluno não paga; com bolsa parcial paga um valor menor; apadrinhada: uma
 * empresa paga 100% da mensalidade (o valor continua na matrícula, mas o responsável não é cobrado)
 */
export type Bolsa = 'nenhuma' | 'parcial' | 'integral' | 'apadrinhada'

export const NOME_DA_BOLSA: Record<Bolsa, string> = {
  nenhuma: 'Sem bolsa',
  parcial: 'Bolsa parcial',
  integral: 'Bolsa integral',
  apadrinhada: 'Apadrinhada',
}

/** A empresa que apadrinha, como aparece junto da matrícula */
export type PadrinhoResumo = {
  id: number
  nome: string
  ativo: boolean
}

export type Matricula = {
  id: number
  aluno: AlunoResumo
  data_inicio: string
  data_encerramento: string | null
  /** Vem como texto ("150.00") para não perder as casas decimais */
  valor_mensalidade: string
  bolsa: Bolsa
  /** Só a matrícula apadrinhada tem empresa */
  padrinho: PadrinhoResumo | null
  situacao: 'ativa' | 'encerrada'
}

export type MatriculaEntrada = {
  aluno_id: number
  data_inicio: string
  bolsa: Bolsa
  valor_mensalidade: string
  /** Obrigatório na bolsa apadrinhada; null nas outras */
  padrinho_id: number | null
}

export type SituacaoMatricula = 'ativas' | 'encerradas' | 'todas'

export function listarMatriculas(
  busca: string,
  situacao: SituacaoMatricula,
  soBolsistas: boolean,
  signal?: AbortSignal,
  padrinhoId?: number | null,
) {
  const parametros = new URLSearchParams({ busca, situacao, so_bolsistas: String(soBolsistas) })
  if (padrinhoId) parametros.set('padrinho_id', String(padrinhoId))
  return apiGet<Matricula[]>(`/api/matriculas?${parametros}`, signal)
}

export function matricularAluno(dados: MatriculaEntrada) {
  return apiEnviar<Matricula>('POST', '/api/matriculas', dados)
}

export function encerrarMatricula(id: number, dataEncerramento: string) {
  return apiEnviar<Matricula>('PATCH', `/api/matriculas/${id}/encerrar`, {
    data_encerramento: dataEncerramento,
  })
}

/** Matrícula ativa do aluno, ou null se ele não tiver nenhuma */
export async function buscarMatriculaAtiva(alunoId: number, signal?: AbortSignal) {
  const parametros = new URLSearchParams({ situacao: 'ativas', aluno_id: String(alunoId) })
  const lista = await apiGet<Matricula[]>(`/api/matriculas?${parametros}`, signal)
  return lista[0] ?? null
}

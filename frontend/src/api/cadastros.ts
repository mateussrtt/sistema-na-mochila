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

// Período do caixa (RF24): de um mês inicial até um mês final, de no máximo 12 meses.
// As regras e as mensagens são as mesmas da API, para o erro aparecer na hora, sem esperar.

import { nomeDoMes, somarMeses } from './formato'

export const MAXIMO_DE_MESES = 12
/** O primeiro mês que a API aceita */
export const PRIMEIRO_MES = '2000-01'

export const ERRO_DE_FORMATO = 'Informe o mês no formato AAAA-MM.'
export const ERRO_ANTIGO = 'Esse mês é antigo demais.'
export const ERRO_NO_FUTURO = 'Escolha o mês atual ou um mês anterior.'
export const ERRO_FIM_ANTES_DO_INICIO = 'O mês final não pode ser antes do mês inicial.'
export const ERRO_MUITOS_MESES = `O período pode ter no máximo ${MAXIMO_DE_MESES} meses.`

const FORMATO = /^[0-9]{4}-(0[1-9]|1[0-2])$/

export type Periodo = { de: string; ate: string }

export type Atalho = 'este-mes' | 'tres-meses' | 'seis-meses' | 'este-ano'

export const ATALHOS: { id: Atalho; rotulo: string }[] = [
  { id: 'este-mes', rotulo: 'Este mês' },
  { id: 'tres-meses', rotulo: 'Últimos 3 meses' },
  { id: 'seis-meses', rotulo: 'Últimos 6 meses' },
  { id: 'este-ano', rotulo: 'Este ano' },
]

/** "2026-11" é um mês; "2026-13", "11/2026" ou texto qualquer não são */
export function mesValido(mes: string): boolean {
  return FORMATO.test(mes)
}

/** Quantos meses há de `de` até `ate`, os dois incluídos: de janeiro a março são 3 */
export function quantidadeDeMeses(de: string, ate: string): number {
  const [anoDe, mesDe] = de.split('-').map(Number)
  const [anoAte, mesAte] = ate.split('-').map(Number)
  return (anoAte - anoDe) * 12 + mesAte - mesDe + 1
}

/** A mensagem do problema do período, ou null se ele está certo. `atual` é o mês de hoje. */
export function erroDoPeriodo(de: string, ate: string, atual: string): string | null {
  if (!mesValido(de) || !mesValido(ate)) return ERRO_DE_FORMATO
  if (de < PRIMEIRO_MES || ate < PRIMEIRO_MES) return ERRO_ANTIGO
  if (de > atual || ate > atual) return ERRO_NO_FUTURO
  if (ate < de) return ERRO_FIM_ANTES_DO_INICIO
  if (quantidadeDeMeses(de, ate) > MAXIMO_DE_MESES) return ERRO_MUITOS_MESES
  return null
}

/** O período de cada atalho. Os "últimos N meses" contam o mês atual como o primeiro. */
export function periodoDoAtalho(atalho: Atalho, atual: string): Periodo {
  switch (atalho) {
    case 'este-mes':
      return { de: atual, ate: atual }
    case 'tres-meses':
      return { de: somarMeses(atual, -2), ate: atual }
    case 'seis-meses':
      return { de: somarMeses(atual, -5), ate: atual }
    case 'este-ano':
      return { de: `${atual.slice(0, 4)}-01`, ate: atual }
  }
}

/**
 * O período lido do endereço da página. Sem `ate`, vale o mês atual; sem `de`, o período é só o
 * mês de `ate`. É o mesmo que a API faz.
 */
export function periodoDoEndereco(de: string | null, ate: string | null, atual: string): Periodo {
  const fim = ate?.trim() || atual
  return { de: de?.trim() || fim, ate: fim }
}

/** "setembro a novembro de 2026", ou "novembro de 2026" se for um mês só */
export function rotuloDoPeriodo(de: string, ate: string): string {
  if (de === ate) return nomeDoMes(de)
  if (de.slice(0, 4) === ate.slice(0, 4)) return `${nomeDoMes(de).split(' de ')[0]} a ${nomeDoMes(ate)}`
  return `${nomeDoMes(de)} a ${nomeDoMes(ate)}`
}

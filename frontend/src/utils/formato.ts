// Funções pequenas de formatação e validação usadas nas telas.

export function iniciais(nome: string): string {
  const partes = nome.trim().split(/\s+/).filter(Boolean)
  if (partes.length === 0) return '?'
  const primeira = partes[0][0]
  const ultima = partes.length > 1 ? partes[partes.length - 1][0] : ''
  return (primeira + ultima).toUpperCase()
}

export function soDigitos(valor: string): string {
  return valor.replace(/\D/g, '')
}

/** Formata enquanto a pessoa digita: (31) 98888-7777 ou (31) 3852-1234 */
export function mascaraTelefone(valor: string): string {
  const d = soDigitos(valor).slice(0, 11)
  if (d.length <= 2) return d.length ? `(${d}` : ''
  if (d.length <= 6) return `(${d.slice(0, 2)}) ${d.slice(2)}`
  if (d.length <= 10) return `(${d.slice(0, 2)}) ${d.slice(2, 6)}-${d.slice(6)}`
  return `(${d.slice(0, 2)}) ${d.slice(2, 7)}-${d.slice(7)}`
}

export function telefoneValido(valor: string): boolean {
  const total = soDigitos(valor).length
  return total === 10 || total === 11
}

/** Só letras e números, em maiúsculas e no máximo 14: o que sobra de um CNPJ digitado */
export function limparCnpj(valor: string): string {
  return valor
    .toUpperCase()
    .replace(/[^0-9A-Z]/g, '')
    .slice(0, 14)
}

/** Formata enquanto a pessoa digita: 11.222.333/0001-81 (também serve para o CNPJ alfanumérico) */
export function mascaraCnpj(valor: string): string {
  const c = limparCnpj(valor)
  const cortes = [0, 2, 5, 8, 12, 14]
  const separadores = ['', '.', '.', '/', '-']
  let saida = ''
  for (let i = 0; i < cortes.length - 1; i++) {
    const trecho = c.slice(cortes[i], cortes[i + 1])
    if (!trecho) break
    saida += separadores[i] + trecho
  }
  return saida
}

const PESOS_CNPJ_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
const PESOS_CNPJ_2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]

function digitoDoCnpj(caracteres: string, pesos: number[]): number {
  // "0" a "9" valem 0 a 9 e "A" a "Z" valem 17 a 42: a conta do CNPJ alfanumérico, que dá o
  // mesmo resultado do CNPJ só com números
  const soma = [...caracteres].reduce((total, c, i) => total + (c.charCodeAt(0) - 48) * pesos[i], 0)
  const resto = soma % 11
  return resto < 2 ? 0 : 11 - resto
}

/** Confere o formato e os dois dígitos verificadores, igual ao servidor */
export function cnpjValido(valor: string): boolean {
  const c = limparCnpj(valor)
  if (!/^[0-9A-Z]{12}[0-9]{2}$/.test(c) || new Set(c).size === 1) return false
  const primeiro = digitoDoCnpj(c.slice(0, 12), PESOS_CNPJ_1)
  const segundo = digitoDoCnpj(c.slice(0, 12) + primeiro, PESOS_CNPJ_2)
  return c.slice(12) === `${primeiro}${segundo}`
}

export function emailValido(valor: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(valor.trim())
}

/** 2014-03-09 → 09/03/2014, sem passar por fuso horário */
export function formatarData(iso: string): string {
  const [ano, mes, dia] = iso.split('-')
  return `${dia}/${mes}/${ano}`
}

/** 2026-11-05T13:30:00Z → 05/11/2026 10:30, sempre no horário de Brasília */
export function formatarDataHora(iso: string): string {
  const data = new Date(iso)
  if (Number.isNaN(data.getTime())) return iso
  return new Intl.DateTimeFormat('pt-BR', {
    timeZone: 'America/Sao_Paulo',
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
    .format(data)
    .replace(',', '')
}

export function idade(iso: string): number {
  const [ano, mes, dia] = iso.split('-').map(Number)
  const hoje = new Date()
  let anos = hoje.getFullYear() - ano
  if (hoje.getMonth() + 1 < mes || (hoje.getMonth() + 1 === mes && hoje.getDate() < dia)) {
    anos -= 1
  }
  return anos
}

export function hojeIso(): string {
  const hoje = new Date()
  const mes = String(hoje.getMonth() + 1).padStart(2, '0')
  const dia = String(hoje.getDate()).padStart(2, '0')
  return `${hoje.getFullYear()}-${mes}-${dia}`
}

/** 150 ou "150.00" → R$ 150,00 */
export function formatarMoeda(valor: string | number): string {
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(Number(valor))
}

/** "150", "150,5" ou "150.50" → número. Devolve null se não for um valor com até 2 casas. */
export function lerValor(texto: string): number | null {
  const limpo = texto.trim()
  if (!/^\d+([.,]\d{1,2})?$/.test(limpo)) return null
  return Number(limpo.replace(',', '.'))
}

/** Valor em reais como número inteiro de centavos, para comparar sem erro de arredondamento */
export function emCentavos(valor: string | number): number {
  return Math.round(Number(valor) * 100)
}

export function plural(total: number, singular: string, plural: string): string {
  return `${total} ${total === 1 ? singular : plural}`
}

/** O mês de hoje no formato AAAA-MM */
export function mesAtualIso(): string {
  return hojeIso().slice(0, 7)
}

const MESES = [
  'janeiro',
  'fevereiro',
  'março',
  'abril',
  'maio',
  'junho',
  'julho',
  'agosto',
  'setembro',
  'outubro',
  'novembro',
  'dezembro',
]

/** 2026-11 → novembro de 2026 */
export function nomeDoMes(mes: string): string {
  const achado = /^([0-9]{4})-(0[1-9]|1[0-2])$/.exec(mes)
  if (!achado) return mes
  return `${MESES[Number(achado[2]) - 1]} de ${achado[1]}`
}

/** 2026-11 → Novembro de 2026 (com a primeira letra maiúscula, para títulos e listas) */
export function nomeDoMesComMaiuscula(mes: string): string {
  const nome = nomeDoMes(mes)
  return nome.charAt(0).toUpperCase() + nome.slice(1)
}

/** Soma meses a um AAAA-MM: somarMeses('2026-12', 1) → '2027-01' */
export function somarMeses(mes: string, quantos: number): string {
  const [ano, numero] = mes.split('-').map(Number)
  const total = ano * 12 + (numero - 1) + quantos
  return `${Math.floor(total / 12)}-${String((total % 12) + 1).padStart(2, '0')}`
}

/** Soma valores em reais ("150.00") sem erro de arredondamento: a conta é feita em centavos */
export function somarValores(valores: string[]): number {
  return valores.reduce((soma, valor) => soma + Math.round(Number(valor) * 100), 0) / 100
}

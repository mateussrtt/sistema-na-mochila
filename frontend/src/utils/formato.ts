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

export function emailValido(valor: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(valor.trim())
}

/** 2014-03-09 → 09/03/2014, sem passar por fuso horário */
export function formatarData(iso: string): string {
  const [ano, mes, dia] = iso.split('-')
  return `${dia}/${mes}/${ano}`
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

export function plural(total: number, singular: string, plural: string): string {
  return `${total} ${total === 1 ? singular : plural}`
}

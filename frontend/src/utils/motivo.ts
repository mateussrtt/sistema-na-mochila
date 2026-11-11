export const MOTIVO_MINIMO = 3
export const MOTIVO_MAXIMO = 255

/** As mesmas regras do servidor para o motivo de isentar, cancelar ou corrigir */
export function erroDoMotivo(motivo: string): string | undefined {
  const limpo = motivo.trim()
  if (!limpo) return 'Informe o motivo.'
  if (limpo.length < MOTIVO_MINIMO) {
    return `Explique o motivo com pelo menos ${MOTIVO_MINIMO} letras.`
  }
  if (limpo.length > MOTIVO_MAXIMO) return `Use no máximo ${MOTIVO_MAXIMO} caracteres.`
}

export const DICA_DO_MOTIVO =
  'Escreva só o necessário: o motivo fica registrado com o seu nome e pode ser visto por quem usa o sistema.'

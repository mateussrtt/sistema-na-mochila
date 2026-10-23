/** Atributos de acessibilidade para ligar o input à mensagem de erro ou dica. */
export function ligacaoDoCampo(id: string, erro?: string, dica?: string) {
  return {
    id,
    'aria-invalid': erro ? true : undefined,
    'aria-describedby': erro ? `${id}-erro` : dica ? `${id}-dica` : undefined,
  }
}

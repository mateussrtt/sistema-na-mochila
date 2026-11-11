/** Quem cancelou um lançamento, quando e por quê (RF17, RF26). O lançamento não é apagado. */
export type Cancelamento = {
  motivo: string
  cancelado_por: string
  /** Data e hora do cancelamento, em ISO 8601 */
  cancelado_em: string
}

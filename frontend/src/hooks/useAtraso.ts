import { useEffect, useState } from 'react'

/** Devolve o valor só depois que ele para de mudar por alguns milissegundos (útil na busca). */
export function useAtraso<T>(valor: T, ms = 250): T {
  const [atrasado, setAtrasado] = useState(valor)

  useEffect(() => {
    const id = window.setTimeout(() => setAtrasado(valor), ms)
    return () => window.clearTimeout(id)
  }, [valor, ms])

  return atrasado
}

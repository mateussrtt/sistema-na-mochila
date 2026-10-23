import { iniciais } from '../utils/formato'

const TONS = ['marinho', 'agua', 'laranja', 'ceu'] as const

type Props = {
  nome: string
  tamanho?: 'p' | 'm'
  apagado?: boolean
}


export default function Monograma({ nome, tamanho = 'm', apagado = false }: Props) {
  let hash = 2166136261
  for (const letra of nome) {
    hash ^= letra.charCodeAt(0)
    hash = Math.imul(hash, 16777619)
  }
  const tom = apagado ? 'cinza' : TONS[(hash >>> 0) % TONS.length]

  return (
    <span className={`monograma monograma-${tamanho} tom-${tom}`} aria-hidden="true">
      {iniciais(nome)}
    </span>
  )
}

import type { ReactNode } from 'react'

type Props = {
  id: string
  rotulo: string
  erro?: string
  dica?: string
  opcional?: boolean
  children: ReactNode
}

/** Rótulo, campo e mensagem de erro logo abaixo. O input recebe o mesmo id. */
export default function Campo({ id, rotulo, erro, dica, opcional, children }: Props) {
  return (
    <div className={`campo${erro ? ' com-erro' : ''}`}>
      <label htmlFor={id}>
        {rotulo}
        {opcional && <span className="opcional"> (opcional)</span>}
      </label>
      {children}
      {erro ? (
        <p className="campo-erro" id={`${id}-erro`} role="alert">
          {erro}
        </p>
      ) : (
        dica && (
          <p className="campo-dica" id={`${id}-dica`}>
            {dica}
          </p>
        )
      )}
    </div>
  )
}

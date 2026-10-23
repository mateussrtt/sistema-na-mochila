import { X } from 'lucide-react'
import { useEffect, useRef, type ReactNode } from 'react'

type Props = {
  aberta: boolean
  titulo: string
  descricao?: string
  aoFechar: () => void
  children: ReactNode
}

/** Painel que desliza da direita com um formulário. Fecha com Esc ou clicando fora. */
export default function Gaveta({ aberta, titulo, descricao, aoFechar, children }: Props) {
  const ref = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const dialogo = ref.current
    if (!dialogo) return
    if (aberta && !dialogo.open) dialogo.showModal()
    if (!aberta && dialogo.open) dialogo.close()
  }, [aberta])

  return (
    <dialog
      ref={ref}
      className="gaveta"
      aria-labelledby="gaveta-titulo"
      onClose={aoFechar}
      onClick={(evento) => {
        if (evento.target === ref.current) aoFechar()
      }}
    >
      {aberta && (
        <div className="gaveta-painel">
          <header className="gaveta-cabecalho">
            <div>
              <h2 id="gaveta-titulo">{titulo}</h2>
              {descricao && <p>{descricao}</p>}
            </div>
            <button type="button" className="botao-icone" aria-label="Fechar" onClick={aoFechar}>
              <X size={20} />
            </button>
          </header>
          {children}
        </div>
      )}
    </dialog>
  )
}

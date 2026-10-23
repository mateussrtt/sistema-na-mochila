import { Check } from 'lucide-react'
import { useEffect } from 'react'

type Props = {
  mensagem: string | null
  aoSumir: () => void
}

/** Confirmação curta no rodapé da tela, que some sozinha. */
export default function Aviso({ mensagem, aoSumir }: Props) {
  useEffect(() => {
    if (!mensagem) return
    const id = window.setTimeout(aoSumir, 3500)
    return () => window.clearTimeout(id)
  }, [mensagem, aoSumir])

  return (
    <div className="aviso-area" role="status" aria-live="polite">
      {mensagem && (
        <p className="aviso" key={mensagem}>
          <Check size={18} aria-hidden="true" />
          {mensagem}
        </p>
      )}
    </div>
  )
}

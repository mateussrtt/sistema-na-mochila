import { Eye, EyeOff } from 'lucide-react'
import { useState } from 'react'

import { ligacaoDoCampo } from '../utils/campo'
import Campo from './Campo'

type Props = {
  id: string
  rotulo: string
  valor: string
  aoMudar: (valor: string) => void
  erro?: string
  dica?: string
  /** "new-password" para senhas novas, "current-password" para a senha atual */
  autoComplete: 'new-password' | 'current-password'
  autoFocus?: boolean
}

/** Campo de senha com o botão de mostrar e esconder o que foi digitado. */
export default function CampoSenha({
  id,
  rotulo,
  valor,
  aoMudar,
  erro,
  dica,
  autoComplete,
  autoFocus,
}: Props) {
  const [visivel, setVisivel] = useState(false)

  return (
    <Campo id={id} rotulo={rotulo} erro={erro} dica={dica}>
      <div className="campo-senha">
        <input
          {...ligacaoDoCampo(id, erro, dica)}
          type={visivel ? 'text' : 'password'}
          autoComplete={autoComplete}
          autoFocus={autoFocus}
          value={valor}
          onChange={(e) => aoMudar(e.target.value)}
        />
        <button
          type="button"
          className="botao-icone"
          aria-label={visivel ? 'Esconder senha' : 'Mostrar senha'}
          aria-pressed={visivel}
          onClick={() => setVisivel((v) => !v)}
        >
          {visivel ? <EyeOff size={18} /> : <Eye size={18} />}
        </button>
      </div>
    </Campo>
  )
}

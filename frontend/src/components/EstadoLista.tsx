import { CircleAlert } from 'lucide-react'
import type { ReactNode } from 'react'

export function Carregando({ linhas = 4 }: { linhas?: number }) {
  return (
    <ul className="lista" aria-busy="true" aria-label="Carregando">
      {Array.from({ length: linhas }, (_, i) => (
        <li key={i} className="linha-esqueleto">
          <span className="esqueleto esqueleto-selo" />
          <span className="esqueleto-textos">
            <span className="esqueleto" style={{ width: `${46 - i * 6}%` }} />
            <span className="esqueleto esqueleto-fino" style={{ width: `${30 + i * 5}%` }} />
          </span>
        </li>
      ))}
    </ul>
  )
}

export function FalhaAoCarregar({ oQue, aoTentar }: { oQue: string; aoTentar: () => void }) {
  return (
    <div className="estado estado-falha" role="alert">
      <CircleAlert size={28} aria-hidden="true" />
      <h3>Não foi possível carregar {oQue}</h3>
      <p>Confira sua conexão e se a API está no ar. Os dados não foram perdidos.</p>
      <button type="button" className="botao botao-secundario" onClick={aoTentar}>
        Tentar de novo
      </button>
    </div>
  )
}

export function Vazio({
  titulo,
  texto,
  children,
}: {
  titulo: string
  texto: string
  children?: ReactNode
}) {
  return (
    <div className="estado">
      <h3>{titulo}</h3>
      <p>{texto}</p>
      {children}
    </div>
  )
}

import { Hammer } from 'lucide-react'
import { Link } from 'react-router'

type Props = {
  titulo: string
}

export default function EmConstrucao({ titulo }: Props) {
  return (
    <section className="pagina">
      <header className="pagina-cabecalho">
        <h1>{titulo}</h1>
      </header>
      <div className="estado">
        <Hammer size={28} aria-hidden="true" />
        <h3>Esta tela ainda está sendo construída</h3>
        <p>Ela entra nas próximas versões do sistema. Enquanto isso, comece pelos cadastros.</p>
        <Link to="/alunos" className="botao botao-secundario">
          Ir para alunos
        </Link>
      </div>
    </section>
  )
}

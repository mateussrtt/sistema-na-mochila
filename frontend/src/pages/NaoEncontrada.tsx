import { Link } from 'react-router'

export default function NaoEncontrada() {
  return (
    <section className="pagina">
      <div className="estado">
        <h3>Esta página não existe</h3>
        <p>O endereço pode ter sido digitado errado ou a página mudou de lugar.</p>
        <Link to="/" className="botao botao-secundario">
          Voltar para o início
        </Link>
      </div>
    </section>
  )
}

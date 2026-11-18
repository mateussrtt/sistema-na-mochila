import type { LinhaDoFluxo } from '../../api/caixa'
import { formatarMoeda, plural } from '../../utils/formato'

type Props = {
  titulo: string
  lado: 'entradas' | 'saidas'
  linhas: LinhaDoFluxo[]
  /** Total do lado (entradas ou saídas), para a parte de cada linha */
  total: string
  vazio: string
}

/** Quanto a linha é do total, arredondado. Uma parte pequena, mas que existe, não vira 0%. */
function parteDoTotal(valor: string, total: string): string {
  const todo = Number(total)
  if (todo <= 0) return '0%'
  const parte = (Number(valor) / todo) * 100
  if (parte > 0 && parte < 1) return 'menos de 1%'
  return `${Math.round(parte)}%`
}

/** Um lado do fluxo de caixa (RF20): cada origem ou categoria, com o valor e a parte do total */
export default function ListaDoFluxo({ titulo, lado, linhas, total, vazio }: Props) {
  const idTitulo = `fluxo-${lado}`
  return (
    <section className={`fluxo-lado fluxo-${lado}`} aria-labelledby={idTitulo}>
      <header className="fluxo-cabecalho">
        <h2 id={idTitulo}>{titulo}</h2>
        <strong>{formatarMoeda(total)}</strong>
      </header>
      {linhas.length === 0 ? (
        <p className="fluxo-vazio">{vazio}</p>
      ) : (
        <ul>
          {linhas.map((linha) => {
            const parte = parteDoTotal(linha.total, total)
            const largura = Math.max((Number(linha.total) / Number(total)) * 100, 1.5)
            return (
              <li key={`${linha.origem}-${linha.categoria_id ?? ''}`}>
                <div className="fluxo-linha">
                  <span className="fluxo-nome">
                    {linha.nome}
                    <span className="mais">
                      {plural(linha.quantidade, 'lançamento', 'lançamentos')} · {parte}
                    </span>
                  </span>
                  <strong>{formatarMoeda(linha.total)}</strong>
                </div>
                <div className="fluxo-barra" aria-hidden="true">
                  <span style={{ width: `${largura}%` }} />
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}

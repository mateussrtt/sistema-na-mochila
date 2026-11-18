import { useEffect, useState } from 'react'

import { consultarPrevisao, type Previsao as PrevisaoDeReceita } from '../../api/previsao'
import { Carregando, FalhaAoCarregar } from '../../components/EstadoLista'
import { formatarMoeda, nomeDoMes, nomeDoMesComMaiuscula, plural } from '../../utils/formato'

function alunos(quantidade: number): string {
  return plural(quantidade, 'aluno pagante', 'alunos pagantes')
}

/** Parte de um valor no todo, de 0 a 100, para a largura das barras */
function parte(valor: string, todo: string): number {
  const total = Number(todo)
  if (total <= 0) return 0
  return Math.min((Number(valor) / total) * 100, 100)
}

/**
 * Previsão de receita (RF21, RF22): quanto deve entrar de mensalidades no mês e nos próximos
 * meses, pelas matrículas em vigor. Patrocínios, editais e doações não entram (RN11).
 */
export default function Previsao() {
  const [previsao, setPrevisao] = useState<PrevisaoDeReceita | null>(null)
  const [falhou, setFalhou] = useState(false)
  const [versao, setVersao] = useState(0)

  useEffect(() => {
    const controle = new AbortController()
    consultarPrevisao(controle.signal)
      .then((dados) => {
        setPrevisao(dados)
        setFalhou(false)
      })
      .catch(() => {
        if (!controle.signal.aborted) setFalhou(true)
      })
    return () => controle.abort()
  }, [versao])

  function recarregar() {
    setFalhou(false)
    setVersao((v) => v + 1)
  }

  const atual = previsao?.atual
  // O mês com a maior previsão define a barra cheia na lista dos 12 meses
  const maior = previsao
    ? Math.max(...previsao.meses.map((m) => Number(m.previsto)), 0).toFixed(2)
    : '0'
  const ultimoMes = previsao?.meses[previsao.meses.length - 1]?.mes.slice(0, 7)

  return (
    <section className="pagina">
      <header className="pagina-cabecalho">
        <h1>Previsão de receita</h1>
        <p>
          Quanto deve entrar de mensalidades, pelas matrículas em vigor. Patrocínios, editais e
          doações não entram, porque não são fixos.
        </p>
      </header>

      {falhou ? (
        <FalhaAoCarregar oQue="a previsão" aoTentar={recarregar} />
      ) : previsao === null || atual === undefined ? (
        <Carregando linhas={2} />
      ) : (
        <>
          <section className="previsao-atual" aria-labelledby="previsao-atual-titulo">
            <header>
              <h2 id="previsao-atual-titulo">{nomeDoMesComMaiuscula(atual.mes.slice(0, 7))}</h2>
              <p>
                Previsto <strong>{formatarMoeda(atual.previsto)}</strong>, de {alunos(atual.alunos)}
              </p>
            </header>

            <div
              className="previsao-progresso"
              role="img"
              aria-label={`Recebido ${formatarMoeda(atual.recebido)} de ${formatarMoeda(atual.previsto)}`}
            >
              <span
                className="progresso-recebido"
                style={{ width: `${parte(atual.recebido, atual.previsto)}%` }}
              />
              <span
                className="progresso-dispensado"
                style={{ width: `${parte(atual.dispensado, atual.previsto)}%` }}
              />
            </div>

            <dl className="previsao-numeros">
              <div className="numero-recebido">
                <dt>Já recebido</dt>
                <dd>{formatarMoeda(atual.recebido)}</dd>
              </div>
              {Number(atual.dispensado) > 0 && (
                <div className="numero-dispensado">
                  <dt>Isento ou cancelado</dt>
                  <dd>{formatarMoeda(atual.dispensado)}</dd>
                </div>
              )}
              <div className="numero-falta">
                <dt>Falta receber</dt>
                <dd>{formatarMoeda(atual.falta)}</dd>
              </div>
            </dl>
          </section>

          <section className="fluxo-lado previsao-meses" aria-labelledby="previsao-meses-titulo">
            <header className="fluxo-cabecalho">
              <h2 id="previsao-meses-titulo">
                Próximos 12 meses, até {ultimoMes ? nomeDoMes(ultimoMes) : ''}
              </h2>
              <strong>{formatarMoeda(previsao.total)}</strong>
            </header>
            <ul>
              {previsao.meses.map((mes, posicao) => (
                <li key={mes.mes} className={posicao === 0 ? 'previsao-mes-atual' : undefined}>
                  <div className="fluxo-linha">
                    <span className="fluxo-nome">
                      {nomeDoMesComMaiuscula(mes.mes.slice(0, 7))}
                      <span className="mais">
                        {alunos(mes.alunos)}
                        {posicao === 0 && ' · mês atual'}
                      </span>
                    </span>
                    <strong>{formatarMoeda(mes.previsto)}</strong>
                  </div>
                  <div className="fluxo-barra" aria-hidden="true">
                    <span style={{ width: `${parte(mes.previsto, maior)}%` }} />
                  </div>
                </li>
              ))}
            </ul>
          </section>

          <p className="nota nota-caixa">
            A previsão considera as matrículas de hoje: quem tem bolsa integral não paga, e o aluno
            apadrinhado é cobrado da empresa. Uma matrícula nova ou encerrada muda a previsão na
            hora.
          </p>
        </>
      )}
    </section>
  )
}

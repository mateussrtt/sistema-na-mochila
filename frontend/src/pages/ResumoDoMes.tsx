import { ChevronRight, TriangleAlert } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router'

import { consultarResumo, type ResumoDoMes as Resumo } from '../api/resumo'
import { Carregando, FalhaAoCarregar } from '../components/EstadoLista'
import { formatarMoeda, nomeDoMes, plural } from '../utils/formato'

function lancamentos(quantidade: number): string {
  return plural(quantidade, 'lançamento', 'lançamentos')
}

type Cartao = {
  /** Para onde o número leva: a tela que o detalha */
  para: string
  rotulo: string
  valor: string
  detalhe: string
  /** Muda a cor do cartão: o saldo negativo e o atraso chamam atenção */
  tom: 'normal' | 'positivo' | 'atencao' | 'negativo'
}

function cartoes(resumo: Resumo): Cartao[] {
  const mes = nomeDoMes(resumo.mes)
  const saldo = Number(resumo.saldo)
  const atraso = resumo.em_atraso
  const emAtraso = Number(atraso.total) > 0
  return [
    {
      para: '/caixa',
      rotulo: `Recebido em ${mes}`,
      valor: formatarMoeda(resumo.recebido.total),
      detalhe: lancamentos(resumo.recebido.quantidade),
      tom: 'normal',
    },
    {
      para: '/pendencias',
      rotulo: 'Em atraso',
      valor: formatarMoeda(atraso.total),
      detalhe: emAtraso
        ? `${plural(atraso.mensalidades, 'mensalidade', 'mensalidades')} · ${plural(atraso.alunos, 'aluno', 'alunos')}`
        : 'Nenhuma mensalidade em atraso',
      tom: emAtraso ? 'atencao' : 'normal',
    },
    {
      para: '/despesas',
      rotulo: `Despesas de ${mes}`,
      valor: formatarMoeda(resumo.despesas.total),
      detalhe: lancamentos(resumo.despesas.quantidade),
      tom: 'normal',
    },
    {
      para: '/caixa',
      rotulo: 'Saldo do mês',
      valor: formatarMoeda(resumo.saldo),
      detalhe:
        saldo < 0 ? 'Saiu mais do que entrou' : saldo > 0 ? 'Fechando no azul' : 'Sem diferença',
      tom: saldo < 0 ? 'negativo' : saldo > 0 ? 'positivo' : 'normal',
    },
  ]
}

/** Os quatro números do mês na tela inicial (RF23). Cada um leva à tela que o detalha. */
export default function ResumoDoMes() {
  const [resumo, setResumo] = useState<Resumo | null>(null)
  const [falhou, setFalhou] = useState(false)
  const [versao, setVersao] = useState(0)

  useEffect(() => {
    const controle = new AbortController()
    consultarResumo(controle.signal)
      .then((dados) => {
        setResumo(dados)
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

  return (
    <section className="resumo-mes" aria-labelledby="resumo-mes-titulo">
      <h2 id="resumo-mes-titulo">{resumo ? `Resumo de ${nomeDoMes(resumo.mes)}` : 'Resumo do mês'}</h2>
      {falhou ? (
        <FalhaAoCarregar oQue="o resumo do mês" aoTentar={recarregar} />
      ) : resumo === null ? (
        <Carregando linhas={2} />
      ) : (
        <ul className="resumo-cartoes">
          {cartoes(resumo).map((cartao) => (
            <li key={cartao.rotulo}>
              <Link to={cartao.para} className={`resumo-cartao resumo-${cartao.tom}`}>
                <span className="resumo-rotulo">
                  {cartao.tom === 'negativo' && <TriangleAlert size={15} aria-hidden="true" />}
                  {cartao.rotulo}
                </span>
                <strong className="resumo-valor">{cartao.valor}</strong>
                <span className="resumo-detalhe">{cartao.detalhe}</span>
                <ChevronRight size={18} className="linha-seta" aria-hidden="true" />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

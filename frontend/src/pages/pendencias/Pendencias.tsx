import { CalendarDays, ChevronLeft, ChevronRight, Mail, Phone } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

import { listarPendencias, type Pendencias as Painel } from '../../api/pendencias'
import { Carregando, FalhaAoCarregar, Vazio } from '../../components/EstadoLista'
import Monograma from '../../components/Monograma'
import {
  formatarData,
  formatarMoeda,
  mascaraTelefone,
  mesAtualIso,
  nomeDoMes,
  nomeDoMesComMaiuscula,
  plural,
  soDigitos,
  somarMeses,
} from '../../utils/formato'

type Modo = 'todos' | 'mes'

function textoDoAtraso(dias: number): string {
  return `${plural(dias, 'dia', 'dias')} de atraso`
}

export default function Pendencias() {
  const [modo, setModo] = useState<Modo>('todos')
  const [mes, setMes] = useState(mesAtualIso)
  // Guarda de qual filtro é o painel. Se o filtro mudou, ele não vale mais e a tela mostra "carregando"
  const [resposta, setResposta] = useState<{ chave: string; painel: Painel } | null>(null)
  const [falhou, setFalhou] = useState(false)
  const [versao, setVersao] = useState(0)

  const filtro = modo === 'mes' ? mes : null
  const chave = filtro ?? 'todos'
  const painel = resposta?.chave === chave ? resposta.painel : null

  useEffect(() => {
    const controle = new AbortController()
    listarPendencias(filtro, controle.signal)
      .then((dados) => {
        setResposta({ chave: filtro ?? 'todos', painel: dados })
        setFalhou(false)
      })
      .catch(() => {
        if (!controle.signal.aborted) setFalhou(true)
      })
    return () => controle.abort()
  }, [filtro, versao])

  const recarregar = useCallback(() => {
    setFalhou(false)
    setVersao((v) => v + 1)
  }, [])

  return (
    <section className="pagina">
      <header className="pagina-cabecalho">
        <h1>Pendências</h1>
        <p>Veja quem está com mensalidade em atraso e como falar com cada responsável.</p>
      </header>

      <div className="barra">
        <div className="segmentos" role="group" aria-label="Período">
          <button type="button" aria-pressed={modo === 'todos'} onClick={() => setModo('todos')}>
            Todos os meses
          </button>
          <button type="button" aria-pressed={modo === 'mes'} onClick={() => setModo('mes')}>
            Um mês
          </button>
        </div>
        {modo === 'mes' && (
          <div className="seletor-mes" role="group" aria-label="Mês">
            <button type="button" aria-label="Mês anterior" onClick={() => setMes(somarMeses(mes, -1))}>
              <ChevronLeft size={18} aria-hidden="true" />
            </button>
            <output aria-live="polite">{nomeDoMes(mes)}</output>
            <button type="button" aria-label="Próximo mês" onClick={() => setMes(somarMeses(mes, 1))}>
              <ChevronRight size={18} aria-hidden="true" />
            </button>
          </div>
        )}
        {modo === 'mes' && mes !== mesAtualIso() && (
          <button type="button" className="botao botao-texto" onClick={() => setMes(mesAtualIso())}>
            Mês atual
          </button>
        )}
      </div>

      {falhou ? (
        <FalhaAoCarregar oQue="as pendências" aoTentar={recarregar} />
      ) : painel === null ? (
        <Carregando />
      ) : painel.grupos.length === 0 ? (
        <Vazio
          titulo={
            filtro
              ? `Nenhuma mensalidade em atraso em ${nomeDoMes(filtro)}`
              : 'Nenhuma mensalidade em atraso'
          }
          texto="Todas as mensalidades vencidas estão pagas, isentas ou canceladas."
        />
      ) : (
        <>
          <dl className="totais">
            <div>
              <dt>Responsáveis em atraso</dt>
              <dd>{painel.resumo.responsaveis}</dd>
            </div>
            <div>
              <dt>Alunos em atraso</dt>
              <dd>{painel.resumo.alunos}</dd>
            </div>
            <div>
              <dt>Mensalidades em atraso</dt>
              <dd>{painel.resumo.mensalidades}</dd>
            </div>
            <div className="totais-atraso">
              <dt>Total em aberto</dt>
              <dd>{formatarMoeda(painel.resumo.total_em_aberto)}</dd>
            </div>
          </dl>

          {/* Um cartão por pendência: cada aluno aparece uma vez só, com todos os seus responsáveis */}
          <ul className="pendencias">
            {painel.grupos.map((g) => (
              <li
                key={g.responsaveis.map((r) => r.id).join('-') || 'sem-responsavel'}
                className="pendencia"
              >
                <div className="pendencia-topo">
                  <div className="pendencia-quem">
                    <h2 className="pendencia-rotulo">
                      {g.responsaveis.length === 1 ? 'Responsável' : 'Responsáveis'}
                    </h2>
                    {g.responsaveis.length === 0 ? (
                      <p className="pendencia-sem-responsavel">Sem responsável cadastrado</p>
                    ) : (
                      <ul className="pendencia-responsaveis">
                        {g.responsaveis.map((r) => (
                          <li key={r.id}>
                            <Monograma nome={r.nome} tamanho="p" />
                            <div>
                              <strong>{r.nome}</strong>
                              <div className="pendencia-contatos">
                                {r.telefone && (
                                  <a href={`tel:${soDigitos(r.telefone)}`}>
                                    <Phone size={14} aria-hidden="true" />
                                    {mascaraTelefone(r.telefone)}
                                  </a>
                                )}
                                {r.email && (
                                  <a href={`mailto:${r.email}`}>
                                    <Mail size={14} aria-hidden="true" />
                                    {r.email}
                                  </a>
                                )}
                              </div>
                            </div>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                  <div className="pendencia-total">
                    <strong>{formatarMoeda(g.total)}</strong>
                    <span>{textoDoAtraso(g.maior_atraso)}</span>
                  </div>
                </div>

                <ul className="pendencia-alunos">
                  {g.alunos.map((a) => (
                    <li key={a.id} className="pendencia-aluno">
                      <div className="pendencia-aluno-nome">
                        <span>
                          {a.nome}
                          {!a.ativo && <span className="etiqueta">Inativo</span>}
                        </span>
                        <span>{formatarMoeda(a.total)}</span>
                      </div>
                      <ul className="pendencia-meses">
                        {a.mensalidades.map((m) => (
                          <li key={m.id}>
                            <span>
                              <CalendarDays size={14} aria-hidden="true" />
                              {nomeDoMesComMaiuscula(m.competencia.slice(0, 7))} · venceu em{' '}
                              {formatarData(m.data_vencimento)}
                            </span>
                            <span>
                              {formatarMoeda(m.valor)} · {textoDoAtraso(m.dias_em_atraso)}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}

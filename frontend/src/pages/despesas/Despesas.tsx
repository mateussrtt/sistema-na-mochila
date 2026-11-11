import { CalendarDays, ChevronLeft, ChevronRight, Plus, Tags, UserRound } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'

import {
  listarCategoriasDespesa,
  listarDespesas,
  type CategoriaDespesa,
  type Despesa,
} from '../../api/despesas'
import Aviso from '../../components/Aviso'
import Busca from '../../components/Busca'
import { Carregando, FalhaAoCarregar, Vazio } from '../../components/EstadoLista'
import Gaveta from '../../components/Gaveta'
import Monograma from '../../components/Monograma'
import { useAtraso } from '../../hooks/useAtraso'
import { useSessao } from '../../sessao/contexto'
import {
  emCentavos,
  formatarData,
  formatarMoeda,
  mesAtualIso,
  nomeDoMes,
  plural,
  somarMeses,
  somarValores,
} from '../../utils/formato'
import CategoriasDespesa from './CategoriasDespesa'
import FormDespesa from './FormDespesa'

type Modo = 'mes' | 'todos'

/** Quanto cada categoria somou na lista, da que mais gastou para a que menos gastou */
function totaisPorCategoria(lista: Despesa[]): { categoria: CategoriaDespesa; centavos: number }[] {
  const soma = new Map<number, { categoria: CategoriaDespesa; centavos: number }>()
  for (const despesa of lista) {
    const atual = soma.get(despesa.categoria.id)
    const centavos = emCentavos(despesa.valor)
    if (atual) atual.centavos += centavos
    else soma.set(despesa.categoria.id, { categoria: despesa.categoria, centavos })
  }
  return [...soma.values()].sort(
    (a, b) => b.centavos - a.centavos || a.categoria.nome.localeCompare(b.categoria.nome),
  )
}

export default function Despesas() {
  const [modo, setModo] = useState<Modo>('mes')
  const [mes, setMes] = useState(mesAtualIso)
  const [categoriaId, setCategoriaId] = useState<number | null>(null)
  const [busca, setBusca] = useState('')
  // Guarda de qual filtro é a lista. Se o filtro mudou, ela não vale mais e a tela mostra "carregando"
  const [resposta, setResposta] = useState<{ chave: string; lista: Despesa[] } | null>(null)
  const [categorias, setCategorias] = useState<CategoriaDespesa[] | null>(null)
  const [falhouLista, setFalhouLista] = useState(false)
  const [falhouCategorias, setFalhouCategorias] = useState(false)
  const [versao, setVersao] = useState(0)
  const [versaoCategorias, setVersaoCategorias] = useState(0)
  const [registrando, setRegistrando] = useState(false)
  const [gerenciando, setGerenciando] = useState(false)
  const [aviso, setAviso] = useState<string | null>(null)
  const buscaAtrasada = useAtraso(busca.trim())
  const { podeEditar } = useSessao()

  const periodo = modo === 'mes' ? mes : ''
  const chave = `${periodo}|${categoriaId ?? ''}|${buscaAtrasada}`
  const lista = resposta?.chave === chave ? resposta.lista : null
  const falhou = falhouLista || falhouCategorias

  useEffect(() => {
    const controle = new AbortController()
    listarDespesas(periodo, categoriaId, buscaAtrasada, controle.signal)
      .then((despesas) => {
        setResposta({ chave: `${periodo}|${categoriaId ?? ''}|${buscaAtrasada}`, lista: despesas })
        setFalhouLista(false)
      })
      .catch(() => {
        if (!controle.signal.aborted) setFalhouLista(true)
      })
    return () => controle.abort()
  }, [periodo, categoriaId, buscaAtrasada, versao])

  useEffect(() => {
    const controle = new AbortController()
    listarCategoriasDespesa('todos', controle.signal)
      .then((todas) => {
        setCategorias(todas)
        setFalhouCategorias(false)
      })
      .catch(() => {
        if (!controle.signal.aborted) setFalhouCategorias(true)
      })
    return () => controle.abort()
  }, [versaoCategorias])

  function recarregar() {
    setFalhouLista(false)
    setFalhouCategorias(false)
    setVersao((v) => v + 1)
    setVersaoCategorias((v) => v + 1)
  }
  const fecharAviso = useCallback(() => setAviso(null), [])

  function aoRegistrar(mensagem: string, data: string) {
    setRegistrando(false)
    setAviso(mensagem)
    // Mostra a despesa nova: se ela é de outro mês, a tela vai para esse mês
    if (modo === 'mes' && data.slice(0, 7) !== mes) setMes(data.slice(0, 7))
    recarregar()
  }

  function aoMudarCategorias(mensagem: string) {
    setAviso(mensagem)
    // O nome e a situação da categoria aparecem também nas despesas já lançadas
    recarregar()
  }

  const ativas = useMemo(() => (categorias ?? []).filter((c) => c.ativo), [categorias])

  const total = useMemo(() => somarValores((lista ?? []).map((d) => d.valor)), [lista])
  const porCategoria = useMemo(() => totaisPorCategoria(lista ?? []), [lista])

  const nomeDoPeriodo = modo === 'mes' ? nomeDoMes(mes) : 'todos os meses'

  const botaoRegistrar = podeEditar && (
    <button
      type="button"
      className="botao botao-principal botao-com-icone"
      disabled={categorias === null}
      onClick={() => setRegistrando(true)}
    >
      <Plus size={18} aria-hidden="true" />
      Registrar despesa
    </button>
  )

  return (
    <section className="pagina">
      <header className="pagina-cabecalho">
        <h1>Despesas</h1>
        <p>Registre o dinheiro que sai da associação e veja para onde ele vai, por categoria.</p>
      </header>

      <div className="barra">
        <div className="segmentos" role="group" aria-label="Período">
          <button type="button" aria-pressed={modo === 'mes'} onClick={() => setModo('mes')}>
            Um mês
          </button>
          <button type="button" aria-pressed={modo === 'todos'} onClick={() => setModo('todos')}>
            Todos os meses
          </button>
        </div>
        {modo === 'mes' && (
          <>
            <div className="seletor-mes" role="group" aria-label="Mês">
              <button
                type="button"
                aria-label="Mês anterior"
                onClick={() => setMes(somarMeses(mes, -1))}
              >
                <ChevronLeft size={18} aria-hidden="true" />
              </button>
              <output aria-live="polite">{nomeDoMes(mes)}</output>
              <button
                type="button"
                aria-label="Próximo mês"
                onClick={() => setMes(somarMeses(mes, 1))}
              >
                <ChevronRight size={18} aria-hidden="true" />
              </button>
            </div>
            {mes !== mesAtualIso() && (
              <button
                type="button"
                className="botao botao-texto"
                onClick={() => setMes(mesAtualIso())}
              >
                Mês atual
              </button>
            )}
          </>
        )}
        <Busca
          id="busca-despesas"
          rotulo="Buscar despesas"
          valor={busca}
          aoMudar={setBusca}
          placeholder="Buscar por descrição ou favorecido"
        />
        {categorias !== null && categorias.length > 0 && (
          <select
            className="filtro-select"
            aria-label="Categoria"
            value={categoriaId ?? ''}
            onChange={(e) => setCategoriaId(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">Todas as categorias</option>
            {categorias.map((c) => (
              <option key={c.id} value={c.id}>
                {c.nome}
                {!c.ativo && ' (inativa)'}
              </option>
            ))}
          </select>
        )}
        {categorias !== null && (
          <button
            type="button"
            className="botao botao-secundario botao-com-icone"
            onClick={() => setGerenciando(true)}
          >
            <Tags size={18} aria-hidden="true" />
            Categorias
          </button>
        )}
        {botaoRegistrar}
      </div>

      {falhou ? (
        <FalhaAoCarregar oQue="as despesas" aoTentar={recarregar} />
      ) : lista === null || categorias === null ? (
        <Carregando />
      ) : lista.length === 0 ? (
        buscaAtrasada ? (
          <Vazio
            titulo={`Nenhuma despesa encontrada para “${buscaAtrasada}”`}
            texto="Confira a grafia da descrição ou do nome de quem recebeu."
          />
        ) : (
          <Vazio
            titulo={
              modo === 'mes' ? `Nenhuma despesa em ${nomeDoMes(mes)}` : 'Nenhuma despesa registrada'
            }
            texto={
              podeEditar
                ? 'Registre as despesas da associação para acompanhar para onde vai o dinheiro.'
                : 'Ainda não há despesas registradas neste período.'
            }
          >
            {botaoRegistrar}
          </Vazio>
        )
      ) : (
        <>
          <dl className="totais totais-dois">
            <div>
              <dt>Total no período</dt>
              <dd>{formatarMoeda(total)}</dd>
            </div>
            <div>
              <dt>Despesas lançadas</dt>
              <dd>{lista.length}</dd>
            </div>
          </dl>

          {categoriaId === null && porCategoria.length > 1 && (
            <section className="por-categoria" aria-label="Total por categoria">
              <h2>Por categoria</h2>
              <ul>
                {porCategoria.map(({ categoria, centavos }) => (
                  <li key={categoria.id}>
                    <span>{categoria.nome}</span>
                    <strong>{formatarMoeda(centavos / 100)}</strong>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <p className="resumo">
            {plural(lista.length, 'despesa', 'despesas')} em {nomeDoPeriodo}
            {buscaAtrasada && ` para “${buscaAtrasada}”`}
          </p>
          <ul className="lista">
            {lista.map((d) => (
              <li key={d.id}>
                <div className="linha linha-parada">
                  <Monograma nome={d.favorecido} />
                  <span className="linha-principal">
                    <span className="linha-titulo linha-titulo-quebra">
                      {d.descricao}
                      <span className="etiqueta">{d.categoria.nome}</span>
                    </span>
                    <span className="linha-detalhes">
                      <span>
                        <CalendarDays size={14} aria-hidden="true" />
                        {formatarData(d.data_despesa)}
                      </span>
                      <span>
                        <UserRound size={14} aria-hidden="true" />
                        Pago a {d.favorecido}
                      </span>
                      <span>Registrada por {d.registrado_por}</span>
                    </span>
                  </span>
                  <span className="linha-lateral">
                    <span className="linha-rotulo">Valor</span>
                    <span>{formatarMoeda(d.valor)}</span>
                  </span>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}

      <Gaveta
        aberta={registrando}
        titulo="Registrar despesa"
        descricao="Dinheiro que saiu da associação, com a categoria e para quem foi pago."
        aoFechar={() => setRegistrando(false)}
      >
        {registrando && (
          <FormDespesa
            categorias={ativas}
            categoriaInicial={categoriaId}
            aoSalvar={aoRegistrar}
            aoCancelar={() => setRegistrando(false)}
            aoCadastrarCategoria={() => {
              setRegistrando(false)
              setGerenciando(true)
            }}
          />
        )}
      </Gaveta>

      <Gaveta
        aberta={gerenciando}
        titulo="Categorias de despesa"
        descricao={
          podeEditar
            ? 'Para onde o dinheiro vai. Cadastre, renomeie ou desative as categorias.'
            : 'Seu perfil pode consultar as categorias, mas não alterar.'
        }
        aoFechar={() => setGerenciando(false)}
      >
        {gerenciando && (
          <CategoriasDespesa
            categorias={categorias ?? []}
            aoMudar={aoMudarCategorias}
            aoFechar={() => setGerenciando(false)}
          />
        )}
      </Gaveta>

      <Aviso mensagem={aviso} aoSumir={fecharAviso} />
    </section>
  )
}

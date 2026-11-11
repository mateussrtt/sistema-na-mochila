import { useState, type FormEvent } from 'react'

import { ApiError } from '../../api/client'
import {
  corrigirDespesa,
  registrarDespesa,
  type CategoriaDespesa,
  type Despesa,
} from '../../api/despesas'
import Campo from '../../components/Campo'
import { ligacaoDoCampo } from '../../utils/campo'
import { formatarMoeda, hojeIso, lerValor } from '../../utils/formato'
import { DICA_DO_MOTIVO, MOTIVO_MAXIMO, erroDoMotivo } from '../../utils/motivo'

type Props = {
  /** Só as categorias ativas: uma inativa não recebe despesas novas */
  categorias: CategoriaDespesa[]
  /** Chamado depois de registrar, com a mensagem de confirmação e a data lançada */
  aoSalvar: (mensagem: string, data: string) => void
  aoCancelar: () => void
  /** Só no registro: na correção, o botão de categorias não aparece */
  aoCadastrarCategoria?: () => void
  /** Categoria já escolhida na tela (filtro), para poupar um clique */
  categoriaInicial?: number | null
  /**
   * Despesa lançada errada que este formulário corrige (só o administrador). Os campos já vêm
   * preenchidos com os dados dela, e o motivo é obrigatório (RF17).
   */
  corrigindo?: Despesa
  /** A API disse que a despesa mudou (ex.: outra pessoa já cancelou): recarrega a lista */
  aoDesatualizar?: () => void
}

type Erros = Partial<
  Record<'data' | 'valor' | 'categoria' | 'descricao' | 'favorecido' | 'motivo' | 'geral', string>
>

const PRIMEIRA_DATA = '2000-01-01'
const DESCRICAO_MINIMA = 3
const DESCRICAO_MAXIMA = 255
const FAVORECIDO_MINIMO = 2
const FAVORECIDO_MAXIMO = 120

function erroDoValor(texto: string): string | undefined {
  const limpo = texto.trim()
  if (!limpo) return 'Informe o valor da despesa.'
  if (limpo.startsWith('-')) return 'O valor da despesa deve ser maior que zero.'
  const valor = lerValor(limpo)
  if (valor === null) return 'Use só números, com até 2 casas decimais. Ex.: 89,90'
  if (valor <= 0) return 'O valor da despesa deve ser maior que zero.'
  if (valor >= 100_000_000) return 'O valor da despesa é alto demais.'
}

/** Espaços repetidos contam como um só, como no servidor */
function limpo(texto: string): string {
  return texto.trim().replace(/\s+/g, ' ')
}

export default function FormDespesa({
  categorias,
  aoSalvar,
  aoCancelar,
  aoCadastrarCategoria,
  categoriaInicial = null,
  corrigindo,
  aoDesatualizar,
}: Props) {
  const [data, setData] = useState(corrigindo?.data_despesa ?? hojeIso())
  const [valor, setValor] = useState(corrigindo?.valor.replace('.', ',') ?? '')
  // Nenhuma categoria vem escolhida (RN08): quem lança precisa decidir para onde o dinheiro foi
  // Na correção, a categoria da errada já vem escolhida, se ainda estiver ativa
  const inicial = corrigindo ? corrigindo.categoria.id : categoriaInicial
  const [categoria, setCategoria] = useState(
    categorias.some((c) => c.id === inicial) ? String(inicial) : '',
  )
  const [descricao, setDescricao] = useState(corrigindo?.descricao ?? '')
  const [favorecido, setFavorecido] = useState(corrigindo?.favorecido ?? '')
  const [motivo, setMotivo] = useState('')
  const [tentou, setTentou] = useState(false)
  const [salvando, setSalvando] = useState(false)
  const [erroApi, setErroApi] = useState<Erros>({})

  function validar(): Erros {
    const erros: Erros = {}
    if (!data) erros.data = 'Informe a data da despesa.'
    else if (data > hojeIso()) erros.data = 'A data da despesa não pode ser no futuro.'
    else if (data < PRIMEIRA_DATA) erros.data = 'Essa data é antiga demais.'
    const erroValor = erroDoValor(valor)
    if (erroValor) erros.valor = erroValor
    if (!categoria) erros.categoria = 'Escolha a categoria da despesa.'
    const textoDescricao = limpo(descricao)
    if (!textoDescricao) erros.descricao = 'Informe a descrição da despesa.'
    else if (textoDescricao.length < DESCRICAO_MINIMA) {
      erros.descricao = `A descrição deve ter pelo menos ${DESCRICAO_MINIMA} letras.`
    } else if (textoDescricao.length > DESCRICAO_MAXIMA) {
      erros.descricao = `Use no máximo ${DESCRICAO_MAXIMA} caracteres.`
    }
    const textoFavorecido = limpo(favorecido)
    if (!textoFavorecido) erros.favorecido = 'Informe para quem foi pago.'
    else if (textoFavorecido.length < FAVORECIDO_MINIMO) {
      erros.favorecido = `O favorecido deve ter pelo menos ${FAVORECIDO_MINIMO} letras.`
    } else if (textoFavorecido.length > FAVORECIDO_MAXIMO) {
      erros.favorecido = `Use no máximo ${FAVORECIDO_MAXIMO} caracteres.`
    }
    if (corrigindo) {
      const erroMotivo = erroDoMotivo(motivo)
      if (erroMotivo) erros.motivo = erroMotivo
    }
    return erros
  }

  const erros: Erros = tentou ? { ...validar(), ...erroApi } : { ...erroApi }

  async function aoEnviar(evento: FormEvent) {
    evento.preventDefault()
    setTentou(true)
    setErroApi({})
    if (Object.keys(validar()).length > 0) return

    setSalvando(true)
    try {
      const dados = {
        data_despesa: data,
        valor: valor.trim().replace(',', '.'),
        categoria_id: Number(categoria),
        descricao: limpo(descricao),
        favorecido: limpo(favorecido),
      }
      const criada = corrigindo
        ? await corrigirDespesa(corrigindo.id, { ...dados, motivo: motivo.trim() })
        : await registrarDespesa(dados)
      aoSalvar(
        `Despesa de ${formatarMoeda(criada.valor)} ${corrigindo ? 'corrigida' : 'registrada'}`,
        criada.data_despesa,
      )
    } catch (erro) {
      const api = erro instanceof ApiError ? erro : null
      const campos = api?.campos ?? {}
      const doServidor: Erros = {}
      if (campos.data_despesa) doServidor.data = campos.data_despesa
      if (campos.valor) doServidor.valor = campos.valor
      if (campos.categoria_id) doServidor.categoria = campos.categoria_id
      if (campos.descricao) doServidor.descricao = campos.descricao
      if (campos.favorecido) doServidor.favorecido = campos.favorecido
      if (campos.motivo) doServidor.motivo = campos.motivo
      if (Object.keys(doServidor).length === 0) {
        // Categoria inativada por outra pessoa enquanto o formulário estava aberto (422 sem campo)
        if (api?.status === 422) doServidor.categoria = api.message
        else doServidor.geral = api?.message ?? 'Não foi possível salvar. Tente de novo.'
      }
      // Outra pessoa já cancelou ou corrigiu esta despesa enquanto o formulário estava aberto
      if (api?.status === 409) aoDesatualizar?.()
      setErroApi(doServidor)
    } finally {
      setSalvando(false)
    }
  }

  const semCategorias = categorias.length === 0

  return (
    <form className="gaveta-formulario" noValidate onSubmit={(e) => void aoEnviar(e)}>
      <div className="gaveta-conteudo">
        {semCategorias && (
          <p className="aviso-valor" role="status">
            Não há categoria ativa. Cadastre uma categoria para poder registrar despesas.
          </p>
        )}

        <div className="campos-lado-a-lado">
          <Campo id="despesa-data" rotulo="Data da despesa" erro={erros.data}>
            <input
              {...ligacaoDoCampo('despesa-data', erros.data)}
              type="date"
              min={PRIMEIRA_DATA}
              max={hojeIso()}
              value={data}
              onChange={(e) => setData(e.target.value)}
            />
          </Campo>
          <Campo id="despesa-valor" rotulo="Valor (R$)" erro={erros.valor}>
            <input
              {...ligacaoDoCampo('despesa-valor', erros.valor)}
              inputMode="decimal"
              placeholder="0,00"
              autoComplete="off"
              value={valor}
              onChange={(e) => setValor(e.target.value)}
            />
          </Campo>
        </div>

        <Campo id="despesa-categoria" rotulo="Categoria" erro={erros.categoria}>
          <select
            {...ligacaoDoCampo('despesa-categoria', erros.categoria)}
            value={categoria}
            onChange={(e) => setCategoria(e.target.value)}
          >
            <option value="">Escolha a categoria…</option>
            {categorias.map((c) => (
              <option key={c.id} value={c.id}>
                {c.nome}
              </option>
            ))}
          </select>
        </Campo>

        <Campo id="despesa-descricao" rotulo="Descrição" erro={erros.descricao}>
          <input
            {...ligacaoDoCampo('despesa-descricao', erros.descricao)}
            placeholder="O que foi comprado ou pago"
            maxLength={DESCRICAO_MAXIMA}
            autoComplete="off"
            value={descricao}
            onChange={(e) => setDescricao(e.target.value)}
          />
        </Campo>

        <Campo id="despesa-favorecido" rotulo="Pago a" erro={erros.favorecido}>
          <input
            {...ligacaoDoCampo('despesa-favorecido', erros.favorecido)}
            placeholder="Pessoa ou empresa que recebeu"
            maxLength={FAVORECIDO_MAXIMO}
            autoComplete="off"
            value={favorecido}
            onChange={(e) => setFavorecido(e.target.value)}
          />
        </Campo>

        {corrigindo ? (
          <CampoDoMotivo
            id="despesa-motivo"
            erro={erros.motivo}
            valor={motivo}
            aoMudar={setMotivo}
          />
        ) : (
          <p className="nota">Depois de registrada, a despesa não pode ser apagada.</p>
        )}

        {erros.geral && (
          <p className="erro-geral" role="alert">
            {erros.geral}
          </p>
        )}
      </div>

      <footer className="gaveta-rodape">
        {aoCadastrarCategoria ? (
          <button type="button" className="botao botao-texto" onClick={aoCadastrarCategoria}>
            {semCategorias ? 'Cadastrar categoria' : 'Categorias…'}
          </button>
        ) : (
          <span />
        )}
        <div className="gaveta-rodape-acoes">
          <button type="button" className="botao botao-texto" onClick={aoCancelar}>
            {corrigindo ? 'Voltar' : 'Cancelar'}
          </button>
          <button
            type="submit"
            className="botao botao-principal"
            disabled={salvando || semCategorias}
          >
            {corrigindo
              ? salvando
                ? 'Salvando…'
                : 'Salvar correção'
              : salvando
                ? 'Registrando…'
                : 'Registrar despesa'}
          </button>
        </div>
      </footer>
    </form>
  )
}

type CampoDoMotivoProps = {
  id: string
  erro?: string
  valor: string
  aoMudar: (valor: string) => void
}

/** Motivo da correção: a despesa errada é cancelada com ele e continua no histórico */
function CampoDoMotivo({ id, erro, valor, aoMudar }: CampoDoMotivoProps) {
  return (
    <>
      <Campo id={id} rotulo="Motivo da correção" erro={erro} dica={DICA_DO_MOTIVO}>
        <input
          {...ligacaoDoCampo(id, erro, DICA_DO_MOTIVO)}
          autoComplete="off"
          maxLength={MOTIVO_MAXIMO}
          value={valor}
          onChange={(e) => aoMudar(e.target.value)}
        />
      </Campo>
      <p className="aviso-valor" role="note">
        A despesa errada não é apagada: fica cancelada, com o motivo, e esta entra no lugar dela.
      </p>
    </>
  )
}

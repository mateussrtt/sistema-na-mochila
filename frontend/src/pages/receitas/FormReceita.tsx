import { useState, type FormEvent } from 'react'

import { ApiError } from '../../api/client'
import {
  corrigirReceita,
  registrarReceita,
  type CategoriaReceita,
  type Receita,
} from '../../api/receitas'
import Campo from '../../components/Campo'
import { ligacaoDoCampo } from '../../utils/campo'
import { formatarMoeda, hojeIso, lerValor } from '../../utils/formato'
import { DICA_DO_MOTIVO, MOTIVO_MAXIMO, erroDoMotivo } from '../../utils/motivo'

type Props = {
  /** Só as categorias ativas: uma inativa não recebe receitas novas */
  categorias: CategoriaReceita[]
  /** Chamado depois de registrar, com a mensagem de confirmação e a data lançada */
  aoSalvar: (mensagem: string, data: string) => void
  aoCancelar: () => void
  /** Só no registro: na correção, o botão de categorias não aparece */
  aoCadastrarCategoria?: () => void
  /** Categoria já escolhida na tela (filtro), para poupar um clique */
  categoriaInicial?: number | null
  /**
   * Receita lançada errada que este formulário corrige (só o administrador). Os campos já vêm
   * preenchidos com os dados dela, e o motivo é obrigatório (RF17).
   */
  corrigindo?: Receita
  /** A API disse que a receita mudou (ex.: outra pessoa já cancelou): recarrega a lista */
  aoDesatualizar?: () => void
}

type Erros = Partial<
  Record<'data' | 'valor' | 'categoria' | 'descricao' | 'origem' | 'motivo' | 'geral', string>
>

const PRIMEIRA_DATA = '2000-01-01'
const DESCRICAO_MINIMA = 3
const DESCRICAO_MAXIMA = 255
const ORIGEM_MINIMO = 2
const ORIGEM_MAXIMO = 120

function erroDoValor(texto: string): string | undefined {
  const limpo = texto.trim()
  if (!limpo) return 'Informe o valor da receita.'
  if (limpo.startsWith('-')) return 'O valor da receita deve ser maior que zero.'
  const valor = lerValor(limpo)
  if (valor === null) return 'Use só números, com até 2 casas decimais. Ex.: 89,90'
  if (valor <= 0) return 'O valor da receita deve ser maior que zero.'
  if (valor >= 100_000_000) return 'O valor da receita é alto demais.'
}

/** Espaços repetidos contam como um só, como no servidor */
function limpo(texto: string): string {
  return texto.trim().replace(/\s+/g, ' ')
}

export default function FormReceita({
  categorias,
  aoSalvar,
  aoCancelar,
  aoCadastrarCategoria,
  categoriaInicial = null,
  corrigindo,
  aoDesatualizar,
}: Props) {
  const [data, setData] = useState(corrigindo?.data_receita ?? hojeIso())
  const [valor, setValor] = useState(corrigindo?.valor.replace('.', ',') ?? '')
  // Nenhuma categoria vem escolhida (RN08): quem lança precisa decidir de onde o dinheiro veio
  // Na correção, a categoria da errada já vem escolhida, se ainda estiver ativa
  const inicial = corrigindo ? corrigindo.categoria.id : categoriaInicial
  const [categoria, setCategoria] = useState(
    categorias.some((c) => c.id === inicial) ? String(inicial) : '',
  )
  const [descricao, setDescricao] = useState(corrigindo?.descricao ?? '')
  const [origem, setOrigem] = useState(corrigindo?.origem ?? '')
  const [motivo, setMotivo] = useState('')
  const [tentou, setTentou] = useState(false)
  const [salvando, setSalvando] = useState(false)
  const [erroApi, setErroApi] = useState<Erros>({})

  function validar(): Erros {
    const erros: Erros = {}
    if (!data) erros.data = 'Informe a data da receita.'
    else if (data > hojeIso()) erros.data = 'A data da receita não pode ser no futuro.'
    else if (data < PRIMEIRA_DATA) erros.data = 'Essa data é antiga demais.'
    const erroValor = erroDoValor(valor)
    if (erroValor) erros.valor = erroValor
    if (!categoria) erros.categoria = 'Escolha a categoria da receita.'
    const textoOrigem = limpo(origem)
    if (!textoOrigem) erros.origem = 'Informe quem pagou.'
    else if (textoOrigem.length < ORIGEM_MINIMO) {
      erros.origem = `A origem deve ter pelo menos ${ORIGEM_MINIMO} letras.`
    } else if (textoOrigem.length > ORIGEM_MAXIMO) {
      erros.origem = `Use no máximo ${ORIGEM_MAXIMO} caracteres.`
    }
    // A descrição é opcional, mas, se vier, segue os mesmos limites do servidor
    const textoDescricao = limpo(descricao)
    if (textoDescricao && textoDescricao.length < DESCRICAO_MINIMA) {
      erros.descricao = `A descrição deve ter pelo menos ${DESCRICAO_MINIMA} letras.`
    } else if (textoDescricao.length > DESCRICAO_MAXIMA) {
      erros.descricao = `Use no máximo ${DESCRICAO_MAXIMA} caracteres.`
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
        data_receita: data,
        valor: valor.trim().replace(',', '.'),
        categoria_id: Number(categoria),
        origem: limpo(origem),
        descricao: limpo(descricao) || null,
      }
      const criada = corrigindo
        ? await corrigirReceita(corrigindo.id, { ...dados, motivo: motivo.trim() })
        : await registrarReceita(dados)
      aoSalvar(
        `Receita de ${formatarMoeda(criada.valor)} ${corrigindo ? 'corrigida' : 'registrada'}`,
        criada.data_receita,
      )
    } catch (erro) {
      const api = erro instanceof ApiError ? erro : null
      const campos = api?.campos ?? {}
      const doServidor: Erros = {}
      if (campos.data_receita) doServidor.data = campos.data_receita
      if (campos.valor) doServidor.valor = campos.valor
      if (campos.categoria_id) doServidor.categoria = campos.categoria_id
      if (campos.descricao) doServidor.descricao = campos.descricao
      if (campos.origem) doServidor.origem = campos.origem
      if (campos.motivo) doServidor.motivo = campos.motivo
      if (Object.keys(doServidor).length === 0) {
        // Categoria inativada por outra pessoa enquanto o formulário estava aberto (422 sem campo)
        if (api?.status === 422) doServidor.categoria = api.message
        else doServidor.geral = api?.message ?? 'Não foi possível salvar. Tente de novo.'
      }
      // Outra pessoa já cancelou ou corrigiu esta receita enquanto o formulário estava aberto
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
            Não há categoria ativa. Cadastre uma categoria para poder registrar receitas.
          </p>
        )}

        <div className="campos-lado-a-lado">
          <Campo id="receita-data" rotulo="Data da receita" erro={erros.data}>
            <input
              {...ligacaoDoCampo('receita-data', erros.data)}
              type="date"
              min={PRIMEIRA_DATA}
              max={hojeIso()}
              value={data}
              onChange={(e) => setData(e.target.value)}
            />
          </Campo>
          <Campo id="receita-valor" rotulo="Valor (R$)" erro={erros.valor}>
            <input
              {...ligacaoDoCampo('receita-valor', erros.valor)}
              inputMode="decimal"
              placeholder="0,00"
              autoComplete="off"
              value={valor}
              onChange={(e) => setValor(e.target.value)}
            />
          </Campo>
        </div>

        <Campo id="receita-categoria" rotulo="Categoria" erro={erros.categoria}>
          <select
            {...ligacaoDoCampo('receita-categoria', erros.categoria)}
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

        <Campo id="receita-origem" rotulo="Quem pagou" erro={erros.origem}>
          <input
            {...ligacaoDoCampo('receita-origem', erros.origem)}
            placeholder="Patrocinador, edital ou quem doou"
            maxLength={ORIGEM_MAXIMO}
            autoComplete="off"
            value={origem}
            onChange={(e) => setOrigem(e.target.value)}
          />
        </Campo>

        <Campo
          id="receita-descricao"
          rotulo="Descrição (opcional)"
          erro={erros.descricao}
          dica="Ex.: nome do projeto, do evento ou da campanha."
        >
          <input
            {...ligacaoDoCampo('receita-descricao', erros.descricao, 'dica')}
            maxLength={DESCRICAO_MAXIMA}
            autoComplete="off"
            value={descricao}
            onChange={(e) => setDescricao(e.target.value)}
          />
        </Campo>

        {corrigindo ? (
          <CampoDoMotivo
            id="receita-motivo"
            erro={erros.motivo}
            valor={motivo}
            aoMudar={setMotivo}
          />
        ) : (
          <p className="nota">
            Mensalidades e pagamentos das empresas padrinhas entram pelas telas próprias, não aqui.
            Depois de registrada, a receita não pode ser apagada.
          </p>
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
                : 'Registrar receita'}
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

/** Motivo da correção: a receita errada é cancelada com ele e continua no histórico */
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
        A receita errada não é apagada: fica cancelada, com o motivo, e esta entra no lugar dela.
      </p>
    </>
  )
}

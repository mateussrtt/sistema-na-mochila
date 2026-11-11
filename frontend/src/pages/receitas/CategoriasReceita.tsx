import { Archive, ArchiveRestore, Check, Pencil } from 'lucide-react'
import { useState, type FormEvent } from 'react'

import { ApiError } from '../../api/client'
import { salvarCategoriaReceita, type CategoriaReceita } from '../../api/receitas'
import Campo from '../../components/Campo'
import { useSessao } from '../../sessao/contexto'
import { ligacaoDoCampo } from '../../utils/campo'

type Props = {
  /** Todas as categorias, ativas e inativas */
  categorias: CategoriaReceita[]
  /** Chamado depois de qualquer mudança, para a tela recarregar as categorias */
  aoMudar: (mensagem: string) => void
  aoFechar: () => void
}

const NOME_MINIMO = 2
const NOME_MAXIMO = 60

function limpo(texto: string): string {
  return texto.trim().replace(/\s+/g, ' ')
}

function erroDoNome(texto: string): string | undefined {
  const nome = limpo(texto)
  if (!nome) return 'Informe o nome da categoria.'
  if (nome.length < NOME_MINIMO) return `O nome deve ter pelo menos ${NOME_MINIMO} letras.`
  if (nome.length > NOME_MAXIMO) return `Use no máximo ${NOME_MAXIMO} caracteres.`
}

/** Mensagem que o servidor mandou (nome repetido, por exemplo) ou uma genérica */
function mensagemDoErro(erro: unknown): string {
  if (erro instanceof ApiError) return erro.campos.nome ?? erro.message
  return 'Não foi possível salvar. Tente de novo.'
}

/** Cadastra, renomeia, desativa e reativa as categorias de receita. Nenhuma é apagada. */
export default function CategoriasReceita({ categorias, aoMudar, aoFechar }: Props) {
  const { podeEditar } = useSessao()
  const [novoNome, setNovoNome] = useState('')
  const [erroNovo, setErroNovo] = useState<string>()
  const [editando, setEditando] = useState<number | null>(null)
  const [nomeEditado, setNomeEditado] = useState('')
  const [erroEdicao, setErroEdicao] = useState<string>()
  const [erroGeral, setErroGeral] = useState<string>()
  // A gaveta cobre o aviso da página: a confirmação também aparece aqui dentro
  const [confirmacao, setConfirmacao] = useState<string>()
  const [ocupado, setOcupado] = useState(false)

  // As ativas primeiro; dentro de cada grupo a ordem alfabética que a API já devolve
  const ordenadas = [...categorias].sort((a, b) => Number(b.ativo) - Number(a.ativo))

  async function adicionar(evento: FormEvent) {
    evento.preventDefault()
    const erro = erroDoNome(novoNome)
    setErroNovo(erro)
    setConfirmacao(undefined)
    if (erro) return

    setOcupado(true)
    try {
      await salvarCategoriaReceita({ nome: limpo(novoNome), ativo: true })
      setNovoNome('')
      setConfirmacao(`Categoria “${limpo(novoNome)}” cadastrada`)
      aoMudar('Categoria cadastrada')
    } catch (falha) {
      setErroNovo(mensagemDoErro(falha))
    } finally {
      setOcupado(false)
    }
  }

  function comecarEdicao(categoria: CategoriaReceita) {
    setEditando(categoria.id)
    setNomeEditado(categoria.nome)
    setErroEdicao(undefined)
    setErroGeral(undefined)
    setConfirmacao(undefined)
  }

  async function salvarEdicao(evento: FormEvent, categoria: CategoriaReceita) {
    evento.preventDefault()
    const erro = erroDoNome(nomeEditado)
    setErroEdicao(erro)
    setErroNovo(undefined)
    setConfirmacao(undefined)
    if (erro) return

    setOcupado(true)
    try {
      await salvarCategoriaReceita(
        { nome: limpo(nomeEditado), ativo: categoria.ativo },
        categoria.id,
      )
      setEditando(null)
      setConfirmacao(`Categoria renomeada para “${limpo(nomeEditado)}”`)
      aoMudar('Categoria atualizada')
    } catch (falha) {
      setErroEdicao(mensagemDoErro(falha))
    } finally {
      setOcupado(false)
    }
  }

  async function alternar(categoria: CategoriaReceita) {
    setErroGeral(undefined)
    setErroNovo(undefined)
    setConfirmacao(undefined)
    setOcupado(true)
    try {
      await salvarCategoriaReceita({ nome: categoria.nome, ativo: !categoria.ativo }, categoria.id)
      setConfirmacao(
        `Categoria “${categoria.nome}” ${categoria.ativo ? 'desativada' : 'reativada'}`,
      )
      aoMudar(categoria.ativo ? 'Categoria desativada' : 'Categoria reativada')
    } catch (falha) {
      setErroGeral(mensagemDoErro(falha))
    } finally {
      setOcupado(false)
    }
  }

  return (
    <div className="gaveta-formulario">
      <div className="gaveta-conteudo">
        {confirmacao && (
          <p className="confirmacao" role="status">
            <Check size={16} aria-hidden="true" />
            {confirmacao}
          </p>
        )}

        {podeEditar && (
          <form className="categoria-nova" noValidate onSubmit={(e) => void adicionar(e)}>
            <Campo id="categoria-nova" rotulo="Nova categoria" erro={erroNovo}>
              <input
                {...ligacaoDoCampo('categoria-nova', erroNovo)}
                value={novoNome}
                maxLength={NOME_MAXIMO}
                placeholder="Ex.: Rifas e eventos"
                autoComplete="off"
                onChange={(e) => setNovoNome(e.target.value)}
              />
            </Campo>
            <button type="submit" className="botao botao-principal" disabled={ocupado}>
              Adicionar
            </button>
          </form>
        )}

        {categorias.length === 0 ? (
          <p className="campo-dica">Nenhuma categoria cadastrada ainda.</p>
        ) : (
          <ul className="categorias">
            {ordenadas.map((categoria) => (
              <li
                key={categoria.id}
                className={categoria.ativo ? 'categoria' : 'categoria inativa'}
              >
                {editando === categoria.id ? (
                  <form
                    className="categoria-edicao"
                    noValidate
                    onSubmit={(e) => void salvarEdicao(e, categoria)}
                  >
                    <Campo
                      id={`categoria-${categoria.id}`}
                      rotulo={`Novo nome de ${categoria.nome}`}
                      erro={erroEdicao}
                    >
                      <input
                        {...ligacaoDoCampo(`categoria-${categoria.id}`, erroEdicao)}
                        value={nomeEditado}
                        maxLength={NOME_MAXIMO}
                        autoComplete="off"
                        onChange={(e) => setNomeEditado(e.target.value)}
                      />
                    </Campo>
                    <div className="categoria-acoes">
                      <button
                        type="button"
                        className="botao botao-texto"
                        onClick={() => setEditando(null)}
                      >
                        Cancelar
                      </button>
                      <button type="submit" className="botao botao-principal" disabled={ocupado}>
                        Salvar
                      </button>
                    </div>
                  </form>
                ) : (
                  <>
                    <span className="categoria-nome">
                      {categoria.nome}
                      {!categoria.ativo && <span className="etiqueta">Inativa</span>}
                    </span>
                    {podeEditar && (
                      <span className="categoria-acoes">
                        <button
                          type="button"
                          className="botao botao-texto botao-com-icone"
                          disabled={ocupado}
                          aria-label={`Renomear ${categoria.nome}`}
                          onClick={() => comecarEdicao(categoria)}
                        >
                          <Pencil size={16} aria-hidden="true" />
                          Renomear
                        </button>
                        <button
                          type="button"
                          className="botao botao-texto botao-com-icone"
                          disabled={ocupado}
                          aria-label={`${categoria.ativo ? 'Desativar' : 'Reativar'} ${categoria.nome}`}
                          onClick={() => void alternar(categoria)}
                        >
                          {categoria.ativo ? (
                            <Archive size={16} aria-hidden="true" />
                          ) : (
                            <ArchiveRestore size={16} aria-hidden="true" />
                          )}
                          {categoria.ativo ? 'Desativar' : 'Reativar'}
                        </button>
                      </span>
                    )}
                  </>
                )}
              </li>
            ))}
          </ul>
        )}

        <p className="nota">
          Uma categoria desativada não recebe receitas novas, mas as que já foram registradas nela
          continuam no histórico. Categorias não são apagadas.
        </p>

        {erroGeral && (
          <p className="erro-geral" role="alert">
            {erroGeral}
          </p>
        )}
      </div>

      <footer className="gaveta-rodape">
        <span />
        <div className="gaveta-rodape-acoes">
          <button type="button" className="botao botao-principal" onClick={aoFechar}>
            Pronto
          </button>
        </div>
      </footer>
    </div>
  )
}

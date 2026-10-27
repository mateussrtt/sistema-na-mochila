import { ArchiveRestore, Archive, UserPlus, X } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent } from 'react'

import {
  buscarMatriculaAtiva,
  salvarAluno,
  type Aluno,
  type Matricula,
  type Responsavel,
} from '../../api/cadastros'
import { ApiError } from '../../api/client'
import Campo from '../../components/Campo'
import Monograma from '../../components/Monograma'
import { useSessao } from '../../sessao/contexto'
import { ligacaoDoCampo } from '../../utils/campo'
import { formatarMoeda, hojeIso } from '../../utils/formato'
import FormResponsavel from './FormResponsavel'
import SeletorResponsavel from './SeletorResponsavel'

type Props = {
  aluno?: Aluno
  aoSalvar: (mensagem: string) => void
  aoCancelar: () => void
}

type Erros = Partial<Record<'nome' | 'data_nascimento' | 'responsaveis' | 'geral', string>>

export default function FormAluno({ aluno, aoSalvar, aoCancelar }: Props) {
  // O perfil de consulta abre o painel só para ver os dados
  const { podeEditar } = useSessao()
  const [nome, setNome] = useState(aluno?.nome ?? '')
  const [nascimento, setNascimento] = useState(aluno?.data_nascimento ?? '')
  const [escola, setEscola] = useState(aluno?.escola ?? '')
  const [municipio, setMunicipio] = useState(aluno?.municipio ?? '')
  const [responsaveis, setResponsaveis] = useState<Responsavel[]>(aluno?.responsaveis ?? [])
  const [novoResponsavel, setNovoResponsavel] = useState<string | null>(null)
  const [tentou, setTentou] = useState(false)
  const [salvando, setSalvando] = useState(false)
  const [erroApi, setErroApi] = useState<Erros>({})
    const [matriculaAtiva, setMatriculaAtiva] = useState<Matricula | null>(null)
  const [confirmandoInativacao, setConfirmandoInativacao] = useState(false)
  const confirmacao = useRef<HTMLDivElement>(null)

  // Ao inativar o aluno, a matrícula ativa dele é encerrada junto. Por isso o painel
  // precisa saber se ela existe, para avisar antes.
  const alunoId = aluno?.id
  const alunoAtivo = aluno?.ativo
  useEffect(() => {
    if (alunoId === undefined || !alunoAtivo) return
    const controle = new AbortController()
    buscarMatriculaAtiva(alunoId, controle.signal)
      .then(setMatriculaAtiva)
      .catch(() => {
        // Sem a consulta, o aviso não aparece, mas a API encerra a matrícula do mesmo jeito
      })
    return () => controle.abort()
  }, [alunoId, alunoAtivo])

  useEffect(() => {
    if (confirmandoInativacao) {
      confirmacao.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    }
  }, [confirmandoInativacao])

  function validar(): Erros {
    const erros: Erros = {}
    if (nome.trim().length < 2) erros.nome = 'Informe o nome completo do aluno.'
    if (nascimento && nascimento > hojeIso()) {
      erros.data_nascimento = 'A data de nascimento não pode ser no futuro.'
    }
    if (responsaveis.length === 0) {
      erros.responsaveis = 'Vincule ao menos um responsável, com telefone ou e-mail.'
    }
    return erros
  }

  const erros: Erros = tentou ? { ...validar(), ...erroApi } : {}

  async function enviar(ativo: boolean, mensagem: string) {
    setTentou(true)
    setErroApi({})
    if (Object.keys(validar()).length > 0) return

    setSalvando(true)
    try {
      await salvarAluno(
        {
          nome,
          data_nascimento: nascimento,
          escola,
          municipio,
          responsavel_ids: responsaveis.map((r) => r.id),
          ativo,
        },
        aluno?.id,
      )
      aoSalvar(mensagem)
    } catch (erro) {
      setErroApi({
        geral:
          erro instanceof ApiError ? erro.message : 'Não foi possível salvar. Tente de novo.',
      })
    } finally {
      setSalvando(false)
    }
  }

  function aoMudarSituacao() {
    if (!aluno) return
    if (!aluno.ativo) {
      void enviar(true, 'Aluno reativado')
    } else if (matriculaAtiva) {
      setConfirmandoInativacao(true)
    } else {
      void enviar(false, 'Aluno inativado')
    }
  }

  function aoEnviar(evento: FormEvent) {
    evento.preventDefault()
    void enviar(aluno?.ativo ?? true, aluno ? 'Alterações salvas' : 'Aluno cadastrado')
  }

  return (
    <form className="gaveta-formulario" noValidate onSubmit={aoEnviar}>
      <fieldset className="gaveta-conteudo" disabled={!podeEditar}>
        <Campo id="aluno-nome" rotulo="Nome do aluno" erro={erros.nome}>
          <input
            {...ligacaoDoCampo('aluno-nome', erros.nome)}
            value={nome}
            autoComplete="off"
            onChange={(e) => setNome(e.target.value)}
          />
        </Campo>

        <Campo
          id="aluno-nascimento"
          rotulo="Data de nascimento"
          erro={erros.data_nascimento}
          opcional
        >
          <input
            {...ligacaoDoCampo('aluno-nascimento', erros.data_nascimento)}
            type="date"
            max={hojeIso()}
            value={nascimento}
            onChange={(e) => setNascimento(e.target.value)}
          />
        </Campo>

        <div className="campos-lado-a-lado">
          <Campo id="aluno-escola" rotulo="Escola" opcional>
            <input
              id="aluno-escola"
              value={escola}
              maxLength={120}
              onChange={(e) => setEscola(e.target.value)}
            />
          </Campo>
          <Campo id="aluno-municipio" rotulo="Município" opcional>
            <input
              id="aluno-municipio"
              value={municipio}
              maxLength={80}
              onChange={(e) => setMunicipio(e.target.value)}
            />
          </Campo>
        </div>

        <fieldset className={`grupo${erros.responsaveis ? ' com-erro' : ''}`}>
          <legend>Responsáveis</legend>

          {responsaveis.length > 0 && (
            <ul className="vinculados">
              {responsaveis.map((r) => (
                <li key={r.id}>
                  <Monograma nome={r.nome} tamanho="p" />
                  <span className="pessoa-texto">
                    <strong>{r.nome}</strong>
                    <span>{[r.telefone, r.email].filter(Boolean).join(', ')}</span>
                  </span>
                  {podeEditar && (
                    <button
                      type="button"
                      className="botao-icone"
                      aria-label={`Desvincular ${r.nome}`}
                      onClick={() => setResponsaveis((lista) => lista.filter((x) => x.id !== r.id))}
                    >
                      <X size={18} />
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}

          {!podeEditar ? null : novoResponsavel === null ? (
            <>
              <SeletorResponsavel
                idsVinculados={responsaveis.map((r) => r.id)}
                invalido={Boolean(erros.responsaveis)}
                aoEscolher={(r) => setResponsaveis((lista) => [...lista, r])}
                aoCriarNovo={setNovoResponsavel}
              />
              {erros.responsaveis && (
                <p className="campo-erro" id="responsaveis-erro" role="alert">
                  {erros.responsaveis}
                </p>
              )}
              <button
                type="button"
                className="botao botao-texto botao-com-icone"
                onClick={() => setNovoResponsavel('')}
              >
                <UserPlus size={18} aria-hidden="true" />
                Cadastrar novo responsável
              </button>
            </>
          ) : (
            <FormResponsavel
              compacto
              nomeInicial={novoResponsavel}
              aoCancelar={() => setNovoResponsavel(null)}
              aoSalvar={(r) => {
                setResponsaveis((lista) => [...lista, r])
                setNovoResponsavel(null)
              }}
            />
          )}
        </fieldset>

        {confirmandoInativacao && aluno && matriculaAtiva && (
          <div className="subformulario" ref={confirmacao} role="alert">
            <h3>Inativar {aluno.nome}?</h3>
            <p>
              A matrícula ativa, de {formatarMoeda(matriculaAtiva.valor_mensalidade)} por mês,
              também será encerrada e deixa de gerar mensalidades. Se o aluno voltar, faça uma
              nova matrícula.
            </p>
            <div className="subformulario-acoes">
              <button
                type="button"
                className="botao botao-texto"
                onClick={() => setConfirmandoInativacao(false)}
              >
                Voltar
              </button>
              <button
                type="button"
                className="botao botao-secundario"
                disabled={salvando}
                onClick={() => void enviar(false, 'Aluno inativado e matrícula encerrada')}
              >
                Inativar e encerrar matrícula
              </button>
            </div>
          </div>
        )}

        {erros.geral && (
          <p className="erro-geral" role="alert">
            {erros.geral}
          </p>
        )}
      </fieldset>

      <footer className="gaveta-rodape">
        {aluno && podeEditar ? (
          <button
            type="button"
            className="botao botao-texto botao-com-icone"
            disabled={salvando || confirmandoInativacao}
            onClick={aoMudarSituacao}
          >
            {aluno.ativo ? (
              <Archive size={18} aria-hidden="true" />
            ) : (
              <ArchiveRestore size={18} aria-hidden="true" />
            )}
            {aluno.ativo ? 'Inativar aluno' : 'Reativar aluno'}
          </button>
        ) : (
          <span />
        )}
        <div className="gaveta-rodape-acoes">
          <button type="button" className="botao botao-texto" onClick={aoCancelar}>
            {podeEditar ? 'Cancelar' : 'Fechar'}
          </button>
          {podeEditar && (
            <button type="submit" className="botao botao-principal" disabled={salvando}>
              {salvando ? 'Salvando…' : aluno ? 'Salvar alterações' : 'Cadastrar aluno'}
            </button>
          )}
        </div>
      </footer>
    </form>
  )
}

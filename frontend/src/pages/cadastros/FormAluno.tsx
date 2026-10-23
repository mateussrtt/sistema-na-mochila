import { ArchiveRestore, Archive, UserPlus, X } from 'lucide-react'
import { useState, type FormEvent } from 'react'

import { salvarAluno, type Aluno, type Responsavel } from '../../api/cadastros'
import { ApiError } from '../../api/client'
import Campo from '../../components/Campo'
import Monograma from '../../components/Monograma'
import { ligacaoDoCampo } from '../../utils/campo'
import { hojeIso } from '../../utils/formato'
import FormResponsavel from './FormResponsavel'
import SeletorResponsavel from './SeletorResponsavel'

type Props = {
  aluno?: Aluno
  aoSalvar: (mensagem: string) => void
  aoCancelar: () => void
}

type Erros = Partial<Record<'nome' | 'data_nascimento' | 'responsaveis' | 'geral', string>>

export default function FormAluno({ aluno, aoSalvar, aoCancelar }: Props) {
  const [nome, setNome] = useState(aluno?.nome ?? '')
  const [nascimento, setNascimento] = useState(aluno?.data_nascimento ?? '')
  const [escola, setEscola] = useState(aluno?.escola ?? '')
  const [municipio, setMunicipio] = useState(aluno?.municipio ?? '')
  const [responsaveis, setResponsaveis] = useState<Responsavel[]>(aluno?.responsaveis ?? [])
  const [novoResponsavel, setNovoResponsavel] = useState<string | null>(null)
  const [tentou, setTentou] = useState(false)
  const [salvando, setSalvando] = useState(false)
  const [erroApi, setErroApi] = useState<Erros>({})

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

  function aoEnviar(evento: FormEvent) {
    evento.preventDefault()
    void enviar(aluno?.ativo ?? true, aluno ? 'Alterações salvas' : 'Aluno cadastrado')
  }

  return (
    <form className="gaveta-formulario" noValidate onSubmit={aoEnviar}>
      <div className="gaveta-conteudo">
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
                  <button
                    type="button"
                    className="botao-icone"
                    aria-label={`Desvincular ${r.nome}`}
                    onClick={() => setResponsaveis((lista) => lista.filter((x) => x.id !== r.id))}
                  >
                    <X size={18} />
                  </button>
                </li>
              ))}
            </ul>
          )}

          {novoResponsavel === null ? (
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

        {erros.geral && (
          <p className="erro-geral" role="alert">
            {erros.geral}
          </p>
        )}
      </div>

      <footer className="gaveta-rodape">
        {aluno ? (
          <button
            type="button"
            className="botao botao-texto botao-com-icone"
            disabled={salvando}
            onClick={() =>
              void enviar(!aluno.ativo, aluno.ativo ? 'Aluno inativado' : 'Aluno reativado')
            }
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
            Cancelar
          </button>
          <button type="submit" className="botao botao-principal" disabled={salvando}>
            {salvando ? 'Salvando…' : aluno ? 'Salvar alterações' : 'Cadastrar aluno'}
          </button>
        </div>
      </footer>
    </form>
  )
}

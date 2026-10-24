import { Plus } from 'lucide-react'
import { useEffect, useState } from 'react'

import { listarAlunos, listarMatriculas, type Aluno } from '../../api/cadastros'
import Monograma from '../../components/Monograma'
import { useAtraso } from '../../hooks/useAtraso'

type Props = {
  aoEscolher: (aluno: Aluno) => void
  invalido: boolean
}

/** Busca um aluno ativo para matricular. Quem já tem matrícula ativa aparece, mas não dá para escolher. */
export default function SeletorAluno({ aoEscolher, invalido }: Props) {
  const [termo, setTermo] = useState('')
  const [resultados, setResultados] = useState<Aluno[] | null>(null)
  const [matriculados, setMatriculados] = useState<Set<number>>(new Set())
  const termoAtrasado = useAtraso(termo.trim())

  useEffect(() => {
    const controle = new AbortController()
    listarMatriculas('', 'ativas', controle.signal)
      .then((lista) => setMatriculados(new Set(lista.map((m) => m.aluno.id))))
      .catch(() => {
        // sem a lista, a API ainda recusa quem já tem matrícula ativa
      })
    return () => controle.abort()
  }, [])

  useEffect(() => {
    if (!termoAtrasado) return
    const controle = new AbortController()
    listarAlunos(termoAtrasado, 'ativos', controle.signal)
      .then(setResultados)
      .catch(() => {
        if (!controle.signal.aborted) setResultados([])
      })
    return () => controle.abort()
  }, [termoAtrasado])

  const opcoes = termoAtrasado ? (resultados ?? []).slice(0, 6) : []

  return (
    <div className="seletor">
      <label htmlFor="busca-aluno" className="so-leitor">
        Buscar aluno ativo
      </label>
      <input
        id="busca-aluno"
        type="search"
        autoComplete="off"
        value={termo}
        placeholder="Buscar aluno pelo nome"
        aria-invalid={invalido || undefined}
        aria-describedby={invalido ? 'aluno-erro' : undefined}
        onChange={(e) => setTermo(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && e.preventDefault()}
      />

      {termoAtrasado && resultados !== null && (
        <ul className="seletor-opcoes">
          {opcoes.length === 0 && (
            <li>
              <p className="seletor-vazio">
                Nenhum aluno ativo encontrado. Cadastre o aluno na aba Alunos.
              </p>
            </li>
          )}
          {opcoes.map((aluno) => {
            const jaMatriculado = matriculados.has(aluno.id)
            return (
              <li key={aluno.id}>
                <button
                  type="button"
                  disabled={jaMatriculado}
                  onClick={() => {
                    aoEscolher(aluno)
                    setTermo('')
                  }}
                >
                  <Monograma nome={aluno.nome} tamanho="p" apagado={jaMatriculado} />
                  <span className="pessoa-texto">
                    <strong>{aluno.nome}</strong>
                    <span>{[aluno.escola, aluno.municipio].filter(Boolean).join(', ')}</span>
                  </span>
                  {jaMatriculado ? (
                    <span className="etiqueta seletor-mais">Já matriculado</span>
                  ) : (
                    <>
                      <Plus size={18} aria-hidden="true" className="seletor-mais" />
                      <span className="so-leitor">Escolher</span>
                    </>
                  )}
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}

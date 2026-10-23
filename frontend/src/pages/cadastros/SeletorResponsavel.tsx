import { Plus, UserPlus } from 'lucide-react'
import { useEffect, useState } from 'react'

import { listarResponsaveis, type Responsavel } from '../../api/cadastros'
import Monograma from '../../components/Monograma'
import { useAtraso } from '../../hooks/useAtraso'

type Props = {
  idsVinculados: number[]
  aoEscolher: (responsavel: Responsavel) => void
  aoCriarNovo: (nome: string) => void
  invalido: boolean
}

/** Busca um responsável já cadastrado para vincular ao aluno. */
export default function SeletorResponsavel({
  idsVinculados,
  aoEscolher,
  aoCriarNovo,
  invalido,
}: Props) {
  const [termo, setTermo] = useState('')
  const [resultados, setResultados] = useState<Responsavel[] | null>(null)
  const termoAtrasado = useAtraso(termo.trim())

  useEffect(() => {
    if (!termoAtrasado) return
    const controle = new AbortController()
    listarResponsaveis(termoAtrasado, controle.signal)
      .then(setResultados)
      .catch(() => {
        if (!controle.signal.aborted) setResultados([])
      })
    return () => controle.abort()
  }, [termoAtrasado])

  const opcoes = termoAtrasado
    ? (resultados ?? []).filter((r) => !idsVinculados.includes(r.id)).slice(0, 5)
    : []

  return (
    <div className="seletor">
      <label htmlFor="busca-responsavel" className="so-leitor">
        Buscar responsável já cadastrado
      </label>
      <input
        id="busca-responsavel"
        type="search"
        autoComplete="off"
        value={termo}
        placeholder="Buscar responsável já cadastrado"
        aria-invalid={invalido || undefined}
        aria-describedby={invalido ? 'responsaveis-erro' : undefined}
        onChange={(e) => setTermo(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && e.preventDefault()}
      />

      {termoAtrasado && resultados !== null && (
        <ul className="seletor-opcoes">
          {opcoes.map((r) => (
            <li key={r.id}>
              <button
                type="button"
                onClick={() => {
                  aoEscolher(r)
                  setTermo('')
                }}
              >
                <Monograma nome={r.nome} tamanho="p" />
                <span className="pessoa-texto">
                  <strong>{r.nome}</strong>
                  <span>{r.telefone ?? r.email}</span>
                </span>
                <Plus size={18} aria-hidden="true" className="seletor-mais" />
                <span className="so-leitor">Vincular</span>
              </button>
            </li>
          ))}
          <li>
            <button
              type="button"
              className="seletor-novo"
              onClick={() => {
                aoCriarNovo(termo.trim())
                setTermo('')
              }}
            >
              <UserPlus size={18} aria-hidden="true" />
              Cadastrar “{termo.trim()}” como novo responsável
            </button>
          </li>
        </ul>
      )}
    </div>
  )
}

import { Plus } from 'lucide-react'
import { useEffect, useState } from 'react'

import { listarPadrinhos, type Padrinho } from '../../api/padrinhos'
import Monograma from '../../components/Monograma'
import { useAtraso } from '../../hooks/useAtraso'
import { mascaraCnpj } from '../../utils/formato'

type Props = {
  aoEscolher: (padrinho: Padrinho) => void
  invalido: boolean
}

/** Escolhe a empresa que vai apadrinhar. Só empresas ativas podem ser escolhidas. */
export default function SeletorPadrinho({ aoEscolher, invalido }: Props) {
  const [termo, setTermo] = useState('')
  const [resultados, setResultados] = useState<Padrinho[] | null>(null)
  const termoAtrasado = useAtraso(termo.trim())

  // Sem digitar nada, já mostra as primeiras empresas ativas: são poucas e ajudam a escolher
  useEffect(() => {
    const controle = new AbortController()
    listarPadrinhos(termoAtrasado, 'ativos', controle.signal)
      .then(setResultados)
      .catch(() => {
        if (!controle.signal.aborted) setResultados([])
      })
    return () => controle.abort()
  }, [termoAtrasado])

  const opcoes = (resultados ?? []).slice(0, 6)

  return (
    <div className="seletor">
      <label htmlFor="busca-padrinho" className="so-leitor">
        Buscar empresa padrinha
      </label>
      <input
        id="busca-padrinho"
        type="search"
        autoComplete="off"
        value={termo}
        placeholder="Buscar a empresa pelo nome"
        aria-invalid={invalido || undefined}
        aria-describedby={invalido ? 'padrinho-erro' : undefined}
        onChange={(e) => setTermo(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && e.preventDefault()}
      />

      {resultados !== null && (
        <ul className="seletor-opcoes">
          {opcoes.length === 0 && (
            <li>
              <p className="seletor-vazio">
                {termoAtrasado
                  ? 'Nenhuma empresa ativa encontrada.'
                  : 'Nenhuma empresa ativa cadastrada.'}{' '}
                Cadastre a empresa na aba Padrinhos.
              </p>
            </li>
          )}
          {opcoes.map((padrinho) => (
            <li key={padrinho.id}>
              <button
                type="button"
                onClick={() => {
                  aoEscolher(padrinho)
                  setTermo('')
                }}
              >
                <Monograma nome={padrinho.nome} tamanho="p" />
                <span className="pessoa-texto">
                  <strong>{padrinho.nome}</strong>
                  <span>
                    {[padrinho.cnpj ? mascaraCnpj(padrinho.cnpj) : null, padrinho.contato]
                      .filter(Boolean)
                      .join(' · ') || `Vencimento no dia ${padrinho.dia_vencimento}`}
                  </span>
                </span>
                <Plus size={18} aria-hidden="true" className="seletor-mais" />
                <span className="so-leitor">Escolher</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

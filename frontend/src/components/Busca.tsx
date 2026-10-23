import { Search, X } from 'lucide-react'

type Props = {
  id: string
  rotulo: string
  valor: string
  aoMudar: (valor: string) => void
  placeholder: string
}

export default function Busca({ id, rotulo, valor, aoMudar, placeholder }: Props) {
  return (
    <div className="busca">
      <label htmlFor={id} className="so-leitor">
        {rotulo}
      </label>
      <Search size={18} className="busca-icone" aria-hidden="true" />
      <input
        id={id}
        type="search"
        value={valor}
        placeholder={placeholder}
        autoComplete="off"
        onChange={(evento) => aoMudar(evento.target.value)}
      />
      {valor && (
        <button
          type="button"
          className="busca-limpar"
          aria-label="Limpar busca"
          onClick={() => aoMudar('')}
        >
          <X size={16} />
        </button>
      )}
    </div>
  )
}

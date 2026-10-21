import { useEffect, useState } from 'react'

import { API_URL, apiGet, type Health } from '../api/client'

type Estado = { tipo: 'carregando' } | { tipo: 'ok'; dados: Health } | { tipo: 'erro' }

export default function Inicio() {
  const [estado, setEstado] = useState<Estado>({ tipo: 'carregando' })

  useEffect(() => {
    const controle = new AbortController()
    apiGet<Health>('/api/health', controle.signal)
      .then((dados) => setEstado({ tipo: 'ok', dados }))
      .catch((erro: unknown) => {
        if (!controle.signal.aborted) {
          console.error(erro)
          setEstado({ tipo: 'erro' })
        }
      })
    return () => controle.abort()
  }, [])

  return (
    <section>
      <h1>Gestão financeira do Na Mochila</h1>
      <p>
        Base do sistema no ar. As telas de alunos, mensalidades, despesas, receitas e caixa
        serão construídas nos próximos ciclos.
      </p>

      <div className="cartao">
        <h2>Situação da API</h2>
        {estado.tipo === 'carregando' && <p>Consultando {API_URL}…</p>}
        {estado.tipo === 'erro' && (
          <p className="alerta">
            Não foi possível falar com a API em {API_URL}. Confira se o backend está rodando e se
            VITE_API_URL está certo.
          </p>
        )}
        {estado.tipo === 'ok' && (
          <ul>
            <li>API: {estado.dados.status}</li>
            <li>Banco de dados: {estado.dados.banco}</li>
          </ul>
        )}
      </div>
    </section>
  )
}

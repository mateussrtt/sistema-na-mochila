import { ChevronRight, UserRound, Users } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router'

import { API_URL, apiGet, type Health } from '../api/client'

type Estado = { tipo: 'carregando' } | { tipo: 'ok'; dados: Health } | { tipo: 'erro' }

function saudacao(): string {
  const hora = new Date().getHours()
  if (hora < 12) return 'Bom dia'
  if (hora < 18) return 'Boa tarde'
  return 'Boa noite'
}

function Indicador({ rotulo, ok, texto }: { rotulo: string; ok: boolean | null; texto: string }) {
  const classe = ok === null ? 'consultando' : ok ? 'ok' : 'falha'
  return (
    <li className="indicador">
      <span className={`ponto ponto-${classe}`} aria-hidden="true" />
      <span>{rotulo}</span>
      <strong>{texto}</strong>
    </li>
  )
}

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

  const apiOk = estado.tipo === 'carregando' ? null : estado.tipo === 'ok'
  const bancoOk =
    estado.tipo === 'carregando' ? null : estado.tipo === 'ok' && estado.dados.banco === 'ok'

  return (
    <section className="pagina">
      <header className="pagina-cabecalho">
        <h1>{saudacao()}</h1>
        <p>
          Este é o painel financeiro do Na Mochila. O cadastro de alunos e responsáveis já está
          disponível; mensalidades, despesas e caixa chegam nas próximas versões.
        </p>
      </header>

      <ul className="atalhos">
        <li>
          <Link to="/alunos" className="atalho">
            <span className="atalho-icone">
              <Users size={22} aria-hidden="true" />
            </span>
            <span className="pessoa-texto">
              <strong>Alunos</strong>
              <span>Cadastre, busque e edite os alunos matriculados</span>
            </span>
            <ChevronRight size={18} className="linha-seta" aria-hidden="true" />
          </Link>
        </li>
        <li>
          <Link to="/alunos/responsaveis" className="atalho">
            <span className="atalho-icone">
              <UserRound size={22} aria-hidden="true" />
            </span>
            <span className="pessoa-texto">
              <strong>Responsáveis</strong>
              <span>Mantenha telefones e e-mails de contato em dia</span>
            </span>
            <ChevronRight size={18} className="linha-seta" aria-hidden="true" />
          </Link>
        </li>
      </ul>

      <section className="situacao" aria-labelledby="situacao-titulo">
        <h2 id="situacao-titulo">Situação do sistema</h2>
        <ul>
          <Indicador
            rotulo="API"
            ok={apiOk}
            texto={apiOk === null ? 'consultando…' : apiOk ? 'no ar' : 'sem resposta'}
          />
          <Indicador
            rotulo="Banco de dados"
            ok={bancoOk}
            texto={bancoOk === null ? 'consultando…' : bancoOk ? 'conectado' : 'indisponível'}
          />
        </ul>
        {estado.tipo === 'erro' && (
          <p className="nota">
            Não foi possível falar com a API em {API_URL}. Se ela ficou um tempo sem uso, pode
            levar até um minuto para acordar. Recarregue a página em seguida.
          </p>
        )}
      </section>
    </section>
  )
}

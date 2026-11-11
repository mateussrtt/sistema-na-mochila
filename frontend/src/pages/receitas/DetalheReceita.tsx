import { useState } from 'react'

import { cancelarReceita, type CategoriaReceita, type Receita } from '../../api/receitas'
import CancelamentoDoLancamento from '../../components/CancelamentoDoLancamento'
import FormMotivo from '../../components/FormMotivo'
import { useSessao } from '../../sessao/contexto'
import { formatarData, formatarDataHora, formatarMoeda } from '../../utils/formato'
import FormReceita from './FormReceita'

type Tela = 'ver' | 'corrigir' | 'cancelar'

type Props = {
  receita: Receita
  /** Só as categorias ativas, para a correção */
  categorias: CategoriaReceita[]
  /** Chamado depois de cancelar ou corrigir, com a mensagem e a data da receita que vale agora */
  aoConcluir: (mensagem: string, data: string) => void
  /** A API disse que a receita mudou (ex.: outra pessoa já cancelou): recarrega a lista */
  aoDesatualizar: () => void
  aoFechar: () => void
}

/**
 * Dados da receita. O administrador corrige (cancela a errada e registra a certa no lugar) ou só
 * cancela, sempre com o motivo (RF17, RN13). Nada é apagado (RN12).
 */
export default function DetalheReceita({
  receita,
  categorias,
  aoConcluir,
  aoDesatualizar,
  aoFechar,
}: Props) {
  const { ehAdmin } = useSessao()
  const [tela, setTela] = useState<Tela>('ver')
  const ativa = receita.cancelamento === null
  const voltar = () => setTela('ver')

  const dados = (
    <>
      <dt>Data</dt>
      <dd>{formatarData(receita.data_receita)}</dd>
      <dt>Valor</dt>
      <dd>{formatarMoeda(receita.valor)}</dd>
      <dt>Categoria</dt>
      <dd>
        {receita.categoria.nome}
        {!receita.categoria.ativo && ' (inativa)'}
      </dd>
      <dt>Quem pagou</dt>
      <dd>{receita.origem}</dd>
      {receita.descricao && (
        <>
          <dt>Descrição</dt>
          <dd>{receita.descricao}</dd>
        </>
      )}
    </>
  )
  const resumo = <dl className="dados">{dados}</dl>

  if (tela === 'corrigir') {
    return (
      <FormReceita
        categorias={categorias}
        corrigindo={receita}
        aoSalvar={aoConcluir}
        aoCancelar={voltar}
        aoDesatualizar={aoDesatualizar}
      />
    )
  }
  if (tela === 'cancelar') {
    return (
      <FormMotivo
        id="cancelar-receita"
        resumo={resumo}
        legenda="Cancelar a receita"
        explicacao="Use quando a receita não deveria ter sido lançada (por exemplo, lançada em dobro). Se só algum dado está errado, use Corrigir. A receita cancelada deixa de contar nos totais."
        botao="Cancelar receita"
        fazendo="Cancelando…"
        enviar={async (motivo) => {
          await cancelarReceita(receita.id, motivo)
          aoConcluir(`Receita de ${formatarMoeda(receita.valor)} cancelada`, receita.data_receita)
        }}
        aoDesatualizar={aoDesatualizar}
        aoVoltar={voltar}
      />
    )
  }

  return (
    <div className="gaveta-formulario">
      <div className="gaveta-conteudo">
        <dl className="dados">
          {dados}
          <dt>Registrada por</dt>
          <dd>
            {receita.registrado_por}, em {formatarDataHora(receita.registrado_em)}
          </dd>
        </dl>

        {receita.substitui_id !== null && (
          <p className="campo-dica">Esta receita é a correção de um lançamento cancelado.</p>
        )}
        {receita.cancelamento && <CancelamentoDoLancamento cancelamento={receita.cancelamento} />}
        {receita.substituida_por_id !== null && (
          <p className="campo-dica">Foi corrigida: a receita certa está na lista no lugar desta.</p>
        )}
      </div>

      <footer className="gaveta-rodape">
        {ativa && ehAdmin ? (
          <button type="button" className="botao botao-texto" onClick={() => setTela('cancelar')}>
            Cancelar receita…
          </button>
        ) : (
          <span />
        )}
        <div className="gaveta-rodape-acoes">
          <button type="button" className="botao botao-texto" onClick={aoFechar}>
            Fechar
          </button>
          {ativa && ehAdmin && (
            <button
              type="button"
              className="botao botao-principal"
              onClick={() => setTela('corrigir')}
            >
              Corrigir
            </button>
          )}
        </div>
      </footer>
    </div>
  )
}

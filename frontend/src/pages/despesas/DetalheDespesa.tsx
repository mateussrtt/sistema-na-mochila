import { useState } from 'react'

import { cancelarDespesa, type CategoriaDespesa, type Despesa } from '../../api/despesas'
import CancelamentoDoLancamento from '../../components/CancelamentoDoLancamento'
import FormMotivo from '../../components/FormMotivo'
import { useSessao } from '../../sessao/contexto'
import { formatarData, formatarDataHora, formatarMoeda } from '../../utils/formato'
import FormDespesa from './FormDespesa'

type Tela = 'ver' | 'corrigir' | 'cancelar'

type Props = {
  despesa: Despesa
  /** Só as categorias ativas, para a correção */
  categorias: CategoriaDespesa[]
  /** Chamado depois de cancelar ou corrigir, com a mensagem e a data da despesa que vale agora */
  aoConcluir: (mensagem: string, data: string) => void
  /** A API disse que a despesa mudou (ex.: outra pessoa já cancelou): recarrega a lista */
  aoDesatualizar: () => void
  aoFechar: () => void
}

/**
 * Dados da despesa. O administrador corrige (cancela a errada e registra a certa no lugar) ou só
 * cancela, sempre com o motivo (RF17, RN13). Nada é apagado (RN12).
 */
export default function DetalheDespesa({
  despesa,
  categorias,
  aoConcluir,
  aoDesatualizar,
  aoFechar,
}: Props) {
  const { ehAdmin } = useSessao()
  const [tela, setTela] = useState<Tela>('ver')
  const ativa = despesa.cancelamento === null
  const voltar = () => setTela('ver')

  const dados = (
    <>
      <dt>Data</dt>
      <dd>{formatarData(despesa.data_despesa)}</dd>
      <dt>Valor</dt>
      <dd>{formatarMoeda(despesa.valor)}</dd>
      <dt>Categoria</dt>
      <dd>
        {despesa.categoria.nome}
        {!despesa.categoria.ativo && ' (inativa)'}
      </dd>
      <dt>Descrição</dt>
      <dd>{despesa.descricao}</dd>
      <dt>Pago a</dt>
      <dd>{despesa.favorecido}</dd>
    </>
  )
  const resumo = <dl className="dados">{dados}</dl>

  if (tela === 'corrigir') {
    return (
      <FormDespesa
        categorias={categorias}
        corrigindo={despesa}
        aoSalvar={aoConcluir}
        aoCancelar={voltar}
        aoDesatualizar={aoDesatualizar}
      />
    )
  }
  if (tela === 'cancelar') {
    return (
      <FormMotivo
        id="cancelar-despesa"
        resumo={resumo}
        legenda="Cancelar a despesa"
        explicacao="Use quando a despesa não deveria ter sido lançada (por exemplo, lançada em dobro). Se só algum dado está errado, use Corrigir. A despesa cancelada deixa de contar nos totais."
        botao="Cancelar despesa"
        fazendo="Cancelando…"
        enviar={async (motivo) => {
          await cancelarDespesa(despesa.id, motivo)
          aoConcluir(`Despesa de ${formatarMoeda(despesa.valor)} cancelada`, despesa.data_despesa)
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
            {despesa.registrado_por}, em {formatarDataHora(despesa.registrado_em)}
          </dd>
        </dl>

        {despesa.substitui_id !== null && (
          <p className="campo-dica">Esta despesa é a correção de um lançamento cancelado.</p>
        )}
        {despesa.cancelamento && <CancelamentoDoLancamento cancelamento={despesa.cancelamento} />}
        {despesa.substituida_por_id !== null && (
          <p className="campo-dica">Foi corrigida: a despesa certa está na lista no lugar desta.</p>
        )}
      </div>

      <footer className="gaveta-rodape">
        {ativa && ehAdmin ? (
          <button type="button" className="botao botao-texto" onClick={() => setTela('cancelar')}>
            Cancelar despesa…
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

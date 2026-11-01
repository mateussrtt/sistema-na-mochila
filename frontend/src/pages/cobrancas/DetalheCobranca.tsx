import { useState } from 'react'

import {
  NOME_DA_FORMA_COBRANCA,
  NOME_DA_SITUACAO_COBRANCA,
  type Cobranca,
} from '../../api/cobrancas'
import { useSessao } from '../../sessao/contexto'
import {
  formatarData,
  formatarDataHora,
  formatarMoeda,
  nomeDoMesComMaiuscula,
  plural,
} from '../../utils/formato'
import CancelarCobranca from './CancelarCobranca'
import FormNota from './FormNota'
import FormPagamentoCobranca from './FormPagamentoCobranca'

type Tela = 'ver' | 'nota' | 'pagamento' | 'cancelar'

type Props = {
  cobranca: Cobranca
  /** Chamado depois de registrar a nota, o pagamento ou cancelar, com a mensagem de confirmação */
  aoConcluir: (mensagem: string) => void
  /** A API disse que a cobrança mudou (ex.: já foi paga por outra pessoa): recarrega a lista */
  aoDesatualizar: () => void
  aoFechar: () => void
}

/** Dados da cobrança e o próximo passo: registrar a nota, registrar o pagamento ou cancelar. */
export default function DetalheCobranca({ cobranca, aoConcluir, aoDesatualizar, aoFechar }: Props) {
  const { podeEditar, ehAdmin } = useSessao()
  const [tela, setTela] = useState<Tela>('ver')

  const voltar = () => setTela('ver')
  if (tela === 'nota') {
    return (
      <FormNota
        cobranca={cobranca}
        aoConcluir={aoConcluir}
        aoDesatualizar={aoDesatualizar}
        aoVoltar={voltar}
      />
    )
  }
  if (tela === 'pagamento') {
    return (
      <FormPagamentoCobranca
        cobranca={cobranca}
        aoConcluir={aoConcluir}
        aoDesatualizar={aoDesatualizar}
        aoVoltar={voltar}
      />
    )
  }
  if (tela === 'cancelar') {
    return (
      <CancelarCobranca
        cobranca={cobranca}
        aoCancelar={aoConcluir}
        aoDesatualizar={aoDesatualizar}
        aoVoltar={voltar}
      />
    )
  }

  const { nota, pagamento } = cobranca
  const aberta = cobranca.status === 'a_emitir' || cobranca.status === 'emitida'

  return (
    <div className="gaveta-formulario">
      <div className="gaveta-conteudo">
        <dl className="dados">
          <dt>Empresa</dt>
          <dd>
            {cobranca.padrinho.nome}
            {!cobranca.padrinho.ativo && ' (inativa)'}
          </dd>
          <dt>Mês</dt>
          <dd>{nomeDoMesComMaiuscula(cobranca.competencia.slice(0, 7))}</dd>
          <dt>Valor</dt>
          <dd>{formatarMoeda(cobranca.valor)}</dd>
          <dt>{cobranca.status === 'a_emitir' ? 'Vencimento sugerido' : 'Vencimento'}</dt>
          <dd>{formatarData(cobranca.data_vencimento)}</dd>
          {cobranca.limite_emissao && cobranca.status === 'a_emitir' && (
            <>
              <dt>Emitir a nota até</dt>
              <dd>
                {formatarData(cobranca.limite_emissao)}
                {cobranca.emissao_atrasada && ' (prazo vencido)'}
              </dd>
            </>
          )}
          <dt>Situação</dt>
          <dd>
            {NOME_DA_SITUACAO_COBRANCA[cobranca.situacao]}
            {cobranca.situacao === 'atrasada' &&
              ` (${plural(cobranca.dias_em_atraso, 'dia', 'dias')})`}
          </dd>
        </dl>

        <fieldset className="grupo">
          <legend>
            {plural(cobranca.alunos.length, 'aluno apadrinhado', 'alunos apadrinhados')}
          </legend>
          <ul className="itens-cobranca">
            {cobranca.alunos.map((item) => (
              <li key={item.mensalidade_id}>
                <span>{item.aluno.nome}</span>
                <span>{formatarMoeda(item.valor)}</span>
              </li>
            ))}
          </ul>
        </fieldset>

        {nota && (
          <fieldset className="grupo">
            <legend>Nota fiscal</legend>
            <dl className="dados">
              <dt>Número</dt>
              <dd>{nota.numero_nota}</dd>
              <dt>Emitida em</dt>
              <dd>{formatarData(nota.data_emissao)}</dd>
              <dt>Registrada por</dt>
              <dd>
                {nota.registrada_por}, em {formatarDataHora(nota.registrada_em)}
              </dd>
            </dl>
          </fieldset>
        )}

        {pagamento && (
          <fieldset className="grupo">
            <legend>Pagamento</legend>
            <dl className="dados">
              <dt>Pago em</dt>
              <dd>{formatarData(pagamento.data_pagamento)}</dd>
              <dt>Valor pago</dt>
              <dd>{formatarMoeda(pagamento.valor_pago)}</dd>
              <dt>Forma</dt>
              <dd>{NOME_DA_FORMA_COBRANCA[pagamento.forma_pagamento]}</dd>
              {pagamento.observacao && (
                <>
                  <dt>Observação</dt>
                  <dd>{pagamento.observacao}</dd>
                </>
              )}
              <dt>Registrado por</dt>
              <dd>
                {pagamento.registrado_por}, em {formatarDataHora(pagamento.registrado_em)}
              </dd>
            </dl>
          </fieldset>
        )}

        {cobranca.motivo && (
          <fieldset className="grupo">
            <legend>Cancelamento</legend>
            <dl className="dados">
              <dt>Motivo</dt>
              <dd>{cobranca.motivo}</dd>
              <dt>Registrado por</dt>
              <dd>
                {cobranca.cancelada_por}
                {cobranca.cancelada_em && `, em ${formatarDataHora(cobranca.cancelada_em)}`}
              </dd>
            </dl>
          </fieldset>
        )}

        {aberta && !podeEditar && (
          <p className="campo-dica">
            Seu perfil só consulta: a nota e o pagamento são registrados por um operador ou
            administrador.
          </p>
        )}
      </div>

      <footer className="gaveta-rodape">
        {aberta && ehAdmin ? (
          <button type="button" className="botao botao-texto" onClick={() => setTela('cancelar')}>
            Cancelar cobrança…
          </button>
        ) : (
          <span />
        )}
        <div className="gaveta-rodape-acoes">
          <button type="button" className="botao botao-texto" onClick={aoFechar}>
            Fechar
          </button>
          {podeEditar && cobranca.status === 'emitida' && (
            <button type="button" className="botao botao-secundario" onClick={() => setTela('nota')}>
              Corrigir nota
            </button>
          )}
          {podeEditar && cobranca.status === 'a_emitir' && (
            <button type="button" className="botao botao-principal" onClick={() => setTela('nota')}>
              Registrar nota
            </button>
          )}
          {podeEditar && cobranca.status === 'emitida' && (
            <button
              type="button"
              className="botao botao-principal"
              onClick={() => setTela('pagamento')}
            >
              Registrar pagamento
            </button>
          )}
        </div>
      </footer>
    </div>
  )
}

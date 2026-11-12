import { Route, Routes } from 'react-router'

import Layout from './components/Layout'
import Cadastros from './pages/cadastros/Cadastros'
import ListaAlunos from './pages/cadastros/ListaAlunos'
import ListaMatriculas from './pages/cadastros/ListaMatriculas'
import ListaPadrinhos from './pages/cadastros/ListaPadrinhos'
import ListaResponsaveis from './pages/cadastros/ListaResponsaveis'
import Entrar from './pages/Entrar'
import Inicio from './pages/Inicio'
import Caixa from './pages/caixa/Caixa'
import Cobrancas from './pages/cobrancas/Cobrancas'
import Despesas from './pages/despesas/Despesas'
import Mensalidades from './pages/mensalidades/Mensalidades'
import NaoEncontrada from './pages/NaoEncontrada'
import Pendencias from './pages/pendencias/Pendencias'
import Receitas from './pages/receitas/Receitas'
import Usuarios from './pages/usuarios/Usuarios'
import RotaProtegida from './sessao/RotaProtegida'

export default function App() {
  return (
    <Routes>
      <Route path="entrar" element={<Entrar />} />
      <Route element={<RotaProtegida />}>
        <Route element={<Layout />}>
          <Route index element={<Inicio />} />
          <Route path="alunos" element={<Cadastros />}>
            <Route index element={<ListaAlunos />} />
            <Route path="responsaveis" element={<ListaResponsaveis />} />
            <Route path="matriculas" element={<ListaMatriculas />} />
            <Route path="padrinhos" element={<ListaPadrinhos />} />
          </Route>
          <Route path="mensalidades" element={<Mensalidades />} />
          <Route path="pendencias" element={<Pendencias />} />
          <Route path="cobrancas" element={<Cobrancas />} />
          <Route path="despesas" element={<Despesas />} />
          <Route path="receitas" element={<Receitas />} />
          <Route path="caixa" element={<Caixa />} />
          <Route path="usuarios" element={<Usuarios />} />
          <Route path="*" element={<NaoEncontrada />} />
        </Route>
      </Route>
    </Routes>
  )
}

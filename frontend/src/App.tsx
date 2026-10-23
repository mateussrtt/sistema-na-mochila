import { Route, Routes } from 'react-router'

import Layout from './components/Layout'
import Cadastros from './pages/cadastros/Cadastros'
import ListaAlunos from './pages/cadastros/ListaAlunos'
import ListaResponsaveis from './pages/cadastros/ListaResponsaveis'
import EmConstrucao from './pages/EmConstrucao'
import Inicio from './pages/Inicio'
import NaoEncontrada from './pages/NaoEncontrada'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Inicio />} />
        <Route path="alunos" element={<Cadastros />}>
          <Route index element={<ListaAlunos />} />
          <Route path="responsaveis" element={<ListaResponsaveis />} />
        </Route>
        <Route path="mensalidades" element={<EmConstrucao titulo="Mensalidades" />} />
        <Route path="despesas" element={<EmConstrucao titulo="Despesas" />} />
        <Route path="receitas" element={<EmConstrucao titulo="Receitas e patrocínios" />} />
        <Route path="caixa" element={<EmConstrucao titulo="Saldo e fluxo de caixa" />} />
        <Route path="*" element={<NaoEncontrada />} />
      </Route>
    </Routes>
  )
}

import { Route, Routes } from 'react-router'

import Layout from './components/Layout'
import Cadastros from './pages/cadastros/Cadastros'
import ListaAlunos from './pages/cadastros/ListaAlunos'
import ListaMatriculas from './pages/cadastros/ListaMatriculas'
import ListaResponsaveis from './pages/cadastros/ListaResponsaveis'
import EmConstrucao from './pages/EmConstrucao'
import Entrar from './pages/Entrar'
import Inicio from './pages/Inicio'
import NaoEncontrada from './pages/NaoEncontrada'
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
          </Route>
          <Route path="mensalidades" element={<EmConstrucao titulo="Mensalidades" />} />
          <Route path="despesas" element={<EmConstrucao titulo="Despesas" />} />
          <Route path="receitas" element={<EmConstrucao titulo="Receitas e patrocínios" />} />
          <Route path="caixa" element={<EmConstrucao titulo="Saldo e fluxo de caixa" />} />
          <Route path="usuarios" element={<Usuarios />} />
          <Route path="*" element={<NaoEncontrada />} />
        </Route>
      </Route>
    </Routes>
  )
}

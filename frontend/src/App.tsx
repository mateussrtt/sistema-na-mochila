import { Route, Routes } from 'react-router'

import Layout from './components/Layout.tsx'
import EmConstrucao from './pages/EmConstrucao'
import Inicio from './pages/Inicio.tsx'
import NaoEncontrada from './pages/NaoEncontrada.tsx'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Inicio />} />
        <Route path="alunos" element={<EmConstrucao titulo="Alunos e responsáveis" />} />
        <Route path="mensalidades" element={<EmConstrucao titulo="Mensalidades" />} />
        <Route path="despesas" element={<EmConstrucao titulo="Despesas" />} />
        <Route path="receitas" element={<EmConstrucao titulo="Receitas e patrocínios" />} />
        <Route path="caixa" element={<EmConstrucao titulo="Saldo e fluxo de caixa" />} />
        <Route path="*" element={<NaoEncontrada />} />
      </Route>
    </Routes>
  )
}

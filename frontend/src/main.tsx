import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles/global.css'
import { App } from './app/App'

const container = document.getElementById('root')
if (!container) throw new Error('#root 요소를 찾을 수 없어요.')

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

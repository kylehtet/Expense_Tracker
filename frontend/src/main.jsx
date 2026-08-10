import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { CustomLogin } from './components/CustomLogin.jsx'
import { CustomSignup } from './components/CustomSignup.jsx'

// /login and /signup are standalone pages that talk to Firebase directly -
// they don't need any of App's auth-gated state.
function Root() {
  const path = window.location.pathname
  if (path === '/login') return <CustomLogin />
  if (path === '/signup') return <CustomSignup />
  return <App />
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <Root />
  </StrictMode>,
)

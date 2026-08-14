import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { CustomLogin } from './components/CustomLogin.jsx'
import { CustomSignup } from './components/CustomSignup.jsx'
import { PrivacyPolicy } from './components/PrivacyPolicy.jsx'

// /login, /signup, and /privacy are standalone pages - /login and /signup
// talk to Firebase directly and don't need any of App's auth-gated state;
// /privacy is just static content, reachable whether or not you're logged in.
function Root() {
  const path = window.location.pathname
  if (path === '/login') return <CustomLogin />
  if (path === '/signup') return <CustomSignup />
  if (path === '/privacy') return <PrivacyPolicy />
  return <App />
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <Root />
  </StrictMode>,
)

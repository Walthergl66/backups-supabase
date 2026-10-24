import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import 'virtual:pwa-register'
import App from './App.jsx'
import { AuthProvider } from './features/auth/AuthContext.jsx'
import { ToastProvider } from './components/ui/Toast.jsx'
import { DialogProvider } from './components/ui/ConfirmDialog.jsx'
import './styles.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <ToastProvider>
        <DialogProvider>
          <AuthProvider>
            <App />
          </AuthProvider>
        </DialogProvider>
      </ToastProvider>
    </BrowserRouter>
  </React.StrictMode>
)
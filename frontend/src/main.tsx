import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import '@fontsource-variable/inter'
import './styles/global.css'
import App from './App.tsx'
import { ToastProvider } from './components/ui/Toast/Toast'

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 2 } },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
      <ToastProvider />
    </QueryClientProvider>
  </StrictMode>,
)

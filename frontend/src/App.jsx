import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext.jsx'
import ProtectedRoute from './components/auth/ProtectedRoute.jsx'
import LoginPage from './components/auth/LoginPage.jsx'
import ChatLayout from './components/chat/ChatLayout.jsx'
import AdminPanel from './components/admin/AdminPanel.jsx'

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public route */}
          <Route path="/" element={<LoginPage />} />

          {/* Protected chat route */}
          <Route
            path="/chat"
            element={
              <ProtectedRoute>
                <ChatLayout />
              </ProtectedRoute>
            }
          />

          {/* Admin route - C-Suite only */}
          <Route
            path="/admin"
            element={
              <ProtectedRoute requiredRole="c_suite">
                <AdminPanel />
              </ProtectedRoute>
            }
          />

          {/* Catch all - redirect to login */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}

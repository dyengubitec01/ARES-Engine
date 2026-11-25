// created by ARES team [2025-12-15]
import { BrowserRouter } from 'react-router-dom';
import { AuthProvider } from './features/auth/AuthContext';
import { ChatRoomsProvider } from './features/chat/ChatRoomsContext';
import { ModalProvider } from './contexts/ModalContext';
import { ThemeProvider } from './contexts/ThemeContext';
import AppRoutes from './routes/AppRoutes';
import MaintenanceOverlay from './components/common/MaintenanceOverlay';
import AppErrorBoundary from './components/common/AppErrorBoundary';
import { FeedbackModalProvider } from './contexts/FeedbackModalContext';
import './App.css';

function App() {
  return (
    <AppErrorBoundary>
      <BrowserRouter>
        <ThemeProvider>
        <ModalProvider>
          <AuthProvider>
            <ChatRoomsProvider>
              <FeedbackModalProvider>
                <MaintenanceOverlay>
                  <AppRoutes />
                </MaintenanceOverlay>
              </FeedbackModalProvider>
            </ChatRoomsProvider>
          </AuthProvider>
        </ModalProvider>
        </ThemeProvider>
      </BrowserRouter>
    </AppErrorBoundary>
  );
}

export default App;


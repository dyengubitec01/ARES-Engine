// created by ARES team [2026-03-17]
import { createContext, useContext, useState, ReactNode, useCallback } from 'react';
import CustomModal from '../components/common/CustomModal';
import { GRADIENT } from '../styles/buttonStyles';

interface ModalConfig {
  type: 'alert' | 'confirm';
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  confirmColor?: string;
  onConfirm?: () => void;
}

interface ModalContextType {
  showAlert: (title: string, message: string, confirmText?: string) => Promise<void>;
  showConfirm: (
    title: string, 
    message: string, 
    onConfirm: () => void | Promise<void>,
    confirmText?: string,
    cancelText?: string,
    confirmColor?: string
  ) => void;
}

const ModalContext = createContext<ModalContextType | undefined>(undefined);

export function ModalProvider({ children }: { children: ReactNode }) {
  const [modalConfig, setModalConfig] = useState<ModalConfig | null>(null);
  const [isOpen, setIsOpen] = useState(false);

  const showAlert = useCallback((title: string, message: string, confirmText: string = '확인'): Promise<void> => {
    return new Promise((resolve) => {
      setModalConfig({
        type: 'alert',
        title,
        message,
        confirmText,
        onConfirm: () => {
          setIsOpen(false);
          setTimeout(() => setModalConfig(null), 200);
          resolve();
        }
      });
      setIsOpen(true);
    });
  }, []);

  const showConfirm = useCallback((
    title: string,
    message: string,
    onConfirm: () => void | Promise<void>,
    confirmText: string = '삭제',
    cancelText: string = '아니오',
    confirmColor: string = GRADIENT.primarySoft
  ) => {
    setModalConfig({
      type: 'confirm',
      title,
      message,
      confirmText,
      cancelText,
      confirmColor,
      onConfirm: async () => {
        setIsOpen(false);
        setTimeout(() => setModalConfig(null), 200);
        await onConfirm();
      }
    });
    setIsOpen(true);
  }, []);

  const handleCancel = useCallback(() => {
    setIsOpen(false);
    setTimeout(() => setModalConfig(null), 200);
  }, []);

  return (
    <ModalContext.Provider value={{ showAlert, showConfirm }}>
      {children}
      {modalConfig && (
        <CustomModal
          isOpen={isOpen}
          type={modalConfig.type}
          title={modalConfig.title}
          message={modalConfig.message}
          confirmText={modalConfig.confirmText}
          cancelText={modalConfig.cancelText}
          confirmColor={modalConfig.confirmColor}
          onConfirm={modalConfig.onConfirm || (() => {})}
          onCancel={modalConfig.type === 'confirm' ? handleCancel : undefined}
        />
      )}
    </ModalContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useModal() {
  const context = useContext(ModalContext);
  if (!context) {
    throw new Error('useModal must be used within a ModalProvider');
  }
  return context;
}

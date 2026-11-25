import { useState, useCallback } from 'react';
import Toast from '../components/common/Toast';
import type { ToastItem } from '../components/common/Toast';

type ToastInput = Omit<ToastItem, 'id'>;

export function useToasts() {
  const [errorToasts, setErrorToasts] = useState<ToastItem[]>([]);
  const [successToasts, setSuccessToasts] = useState<ToastItem[]>([]);

  const showError = useCallback((toast: ToastInput) => {
    setErrorToasts(prev => [...prev, { ...toast, id: Date.now().toString() }]);
  }, []);

  const showSuccess = useCallback((toast: ToastInput) => {
    setSuccessToasts(prev => [...prev, { ...toast, id: Date.now().toString() }]);
  }, []);

  const closeError = useCallback((id: string) => {
    setErrorToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  const closeSuccess = useCallback((id: string) => {
    setSuccessToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  const ToastStack = (
    <>
      {errorToasts.length > 0 && <Toast variant="error" items={errorToasts} onClose={closeError} />}
      {successToasts.length > 0 && <Toast variant="success" items={successToasts} onClose={closeSuccess} />}
    </>
  );

  return { showError, showSuccess, ToastStack };
}
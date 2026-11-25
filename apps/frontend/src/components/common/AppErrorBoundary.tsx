import { Component, ErrorInfo, ReactNode } from 'react';
import { faro } from '@grafana/faro-web-sdk';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
}

class AppErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    try {
      faro?.api?.pushError(error, {
        context: {
          componentStack: info.componentStack ?? '',
        },
      });
    } catch {
      // 모니터링 실패가 fallback UI 표시를 막아서는 안 됨
    }
  }

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <div style={{ padding: '40px', textAlign: 'center' }}>
          <h2>일시적인 오류가 발생했습니다.</h2>
          <p>잠시 후 다시 시도해 주세요.</p>
          <button onClick={() => window.location.reload()}>새로고침</button>
        </div>
      );
    }
    return this.props.children;
  }
}

export default AppErrorBoundary;

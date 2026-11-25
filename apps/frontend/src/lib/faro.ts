import { initializeFaro, getWebInstrumentations, faro } from '@grafana/faro-web-sdk';

let initialized = false;

export function initFaro(): void {
  if (initialized) return;

  const url = import.meta.env.VITE_FARO_URL;
  if (!url) {
    console.warn('[faro] VITE_FARO_URL not set — frontend telemetry disabled');
    return;
  }

  initializeFaro({
    url,
    app: {
      name: 'ares-frontend',
      version: import.meta.env.VITE_APP_VERSION || 'unknown',
      environment: import.meta.env.MODE,
    },
    instrumentations: [
      ...getWebInstrumentations({
        captureConsole: true,
      }),
    ],
  });

  initialized = true;
}

export function setFaroUser(user: {
  id: string;
  email?: string;
  attributes?: Record<string, string>;
}): void {
  if (!initialized) return;
  faro.api.setUser({
    id: user.id,
    email: user.email,
    attributes: user.attributes,
  });
}

export function clearFaroUser(): void {
  if (!initialized) return;
  faro.api.resetUser();
}

export function reportApiError(params: {
  url: string;
  method: string;
  status: number | undefined;
  backendCode?: string;
  backendMessage?: string;
  isRefreshFailure?: boolean;
}): void {
  if (!initialized) return;
  try {
    faro.api.pushEvent('api_error', {
      url: params.url,
      method: params.method.toUpperCase(),
      status: String(params.status ?? 'network'),
      backendCode: params.backendCode ?? '',
      backendMessage: params.backendMessage ?? '',
      isRefreshFailure: params.isRefreshFailure ? 'true' : 'false',
    });
  } catch {
    // 모니터링 실패가 앱 동작을 막아서는 안 됨
  }
}

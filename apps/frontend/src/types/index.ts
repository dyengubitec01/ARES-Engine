// created by ARES team [2025-12-15]
// 공통 타입 정의
export interface ApiResponse<T = unknown> {
  success: boolean;
  message: string;
  data?: T;
}

export interface User {
  id: string;
  email: string;
  name: string;
  role: 'user' | 'admin';
}

// created by ARES team [2026-01-30]
import { AdminUser, Authority, AdminDocument, PaginationMeta } from '../../services/admin.service';

export interface AdminUserManagementProps {
  users: AdminUser[];
  isLoading: boolean;
  error: string | null;
  meta: PaginationMeta | null;
  currentPage: number;
  onPageChange: (page: number) => void;
}

export interface AdminAuthorityProps {
  users: AdminUser[];
  authorities: Authority[];
  isLoading: boolean;
  error: string | null;
  processingUserId: string | null;
  onToggleAuthority: (userId: string, authorityName: string, shouldGrant: boolean) => void;
}

export interface AdminDocumentStorageProps {
  adminDocuments: AdminDocument[];
  isLoading: boolean;
  error: string | null;
  sortOrder: 'desc' | 'asc';
  onSortToggle: () => void;
  onRefreshDocuments: () => Promise<void>;
  meta: PaginationMeta | null;
  currentPage: number;
  onPageChange: (page: number) => void;
}

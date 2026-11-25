// created by ARES team [2026-01-30]
import { AdminUser, Authority, PaginationMeta } from '../../services/admin.service';
import Pagination from '../../components/common/Pagination';
import { adminHeaderCellStyle, adminTableStyle, adminTitleStyle, adminCellStyle } from '../../styles/tableStyles';
import TableSkeleton from '../../components/common/TableSkeleton';
import Checkbox from '../../components/common/Checkbox';

interface AdminAuthorityProps {
  users: AdminUser[];
  authorities: Authority[];
  isLoading: boolean;
  error: string | null;
  processingUserId: string | null;
  onToggleAuthority: (userId: string, authorityName: string, shouldGrant: boolean) => void;
  meta: PaginationMeta | null;
  currentPage: number;
  onPageChange: (page: number) => void;
}

function AdminAuthority({
  users,
  authorities,
  isLoading,
  error,
  processingUserId,
  onToggleAuthority,
  meta,
  currentPage,
  onPageChange
}: AdminAuthorityProps) {
  // 체크박스 변경 핸들러
  const handleCheckboxChange = (userId: string, authorityName: string, currentlyHas: boolean) => {
    const shouldGrant = !currentlyHas;
    onToggleAuthority(userId, authorityName, shouldGrant);
  };

  return (
    <div style={{ flex: 1, padding: '0 20px 19px', overflowY: 'auto' }}>
      <div style={{ padding: '19px 20px 0 20px' }}>
        <h2 style={{ ...adminTitleStyle, margin: '0 0 33px 0' }}>
          사용자 목록
        </h2>
      </div>

        {isLoading ? (
          <TableSkeleton />
        ) : error ? (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--color-error-500)' }}>
            {error}
          </div>
        ) : users.length === 0 ? (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--color-grayscale-500)' }}>
            등록된 사용자가 없습니다.
          </div>
        ) : (
          <>
            <div style={{ overflowX: 'auto', padding: '0 20px' }}>
              <table style={adminTableStyle}>
                <thead>
                  <tr style={{ height: '36px' }}>
                    <th style={{ ...adminHeaderCellStyle, textAlign: 'left', minWidth: '120px', borderTopLeftRadius: '10px' }}>
                      이름
                    </th>
                    <th style={{ ...adminHeaderCellStyle, textAlign: 'left', minWidth: '200px' }}>
                      이메일
                    </th>
                    {authorities.map((auth, index) => (
                      <th
                        key={auth.id}
                        style={{
                          ...adminHeaderCellStyle,
                          minWidth: '100px',
                          ...(index === authorities.length - 1 ? { borderTopRightRadius: '10px' } : {}),
                        }}
                      >
                        {auth.authorityName}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {users.map((userItem) => {
                    const isProcessing = processingUserId === userItem.id;

                    return (
                      <tr key={userItem.id} style={{ height: '52px' }}>
                        <td style={{ ...adminCellStyle, color: 'var(--color-grayscale-900)' }}>
                          {userItem.name}
                        </td>
                        <td style={{ ...adminCellStyle, color: 'var(--color-grayscale-500)' }}>
                          {userItem.email}
                        </td>
                        {authorities.map((auth) => {
                          const hasAuthority = userItem.authorities.includes(auth.authorityName);

                          return (
                            <td
                              key={auth.id}
                              style={{ ...adminCellStyle, textAlign: 'center' }}
                            >
                              <Checkbox
                                checked={hasAuthority}
                                disabled={isProcessing}
                                onChange={() => handleCheckboxChange(userItem.id, auth.authorityName, hasAuthority)}
                                size={18}
                              />
                            </td>
                          );
                        })}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {meta && meta.total > 0 && (
              <Pagination
                currentPage={currentPage}
                totalItems={meta.total}
                itemsPerPage={meta.limit}
                onPageChange={onPageChange}
                itemLabel="명"
              />
            )}
          </>
        )}
    </div>
  );
}

export default AdminAuthority;

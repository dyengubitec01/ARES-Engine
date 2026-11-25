// created by ARES team [2026-01-30]
import { useState, useEffect, useRef } from 'react';
import { AdminUser, PaginationMeta, Department, updateDeptPermissions, getAdminDepartments } from '../../services/admin.service';
import Pagination from '../../components/common/Pagination';
import { adminHeaderCellStyle, adminTableStyle, adminTitleStyle, adminCellStyle } from '../../styles/tableStyles';
import SearchIcon from '../../assets/icons/search.svg?react';
import { deptAddIcon, deptAdd2Icon } from '../../assets/admin';
import { useModal } from '../../contexts/ModalContext';
import DeptAddModal from './DeptAddModal';
import Checkbox from '../../components/common/Checkbox';
import TableSkeleton from '../../components/common/TableSkeleton';

const AVATAR_BG_COLORS = ['#F6EFB8', '#DAF6B8', '#F9DBF3', '#B8CEF6', '#BEEAEA'];

function getAvatarBgColor(name: string) {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  return AVATAR_BG_COLORS[Math.abs(hash) % AVATAR_BG_COLORS.length];
}

interface AdminUserManagementProps {
  users: AdminUser[];
  isLoading: boolean;
  error: string | null;
  meta: PaginationMeta | null;
  currentPage: number;
  onPageChange: (page: number) => void;
  onRefreshUsers?: () => void;
  onSearch?: (query: string) => void;
}

function AdminUserManagement({
  users,
  isLoading,
  error,
  meta,
  currentPage,
  onPageChange,
  onRefreshUsers,
  onSearch
}: AdminUserManagementProps) {
  const [isDeptModalOpen, setIsDeptModalOpen] = useState(false);
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [checkedUserIds, setCheckedUserIds] = useState<Set<string>>(new Set());
  const [isDeptDropdownOpen, setIsDeptDropdownOpen] = useState(false);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [isBatchProcessing, setIsBatchProcessing] = useState(false);
  const deptDropdownRef = useRef<HTMLDivElement>(null);
  const { showAlert } = useModal();

  const selectedUser = users.find((u) => u.id === selectedUserId);

  const allChecked = users.length > 0 && users.every((u) => checkedUserIds.has(u.id));

  const handleToggleAll = () => {
    if (allChecked) {
      setCheckedUserIds(new Set());
    } else {
      setCheckedUserIds(new Set(users.map((u) => u.id)));
    }
  };

  const handleToggleUser = (userId: string) => {
    setCheckedUserIds((prev) => {
      const next = new Set(prev);
      if (next.has(userId)) {
        next.delete(userId);
      } else {
        next.add(userId);
      }
      return next;
    });
  };

  const handleDeptConfirm = async (deptIds: string[]) => {
    if (!selectedUserId) return;
    try {
      await updateDeptPermissions(selectedUserId, deptIds);
      setIsDeptModalOpen(false);
      onRefreshUsers?.();
    } catch {
      // apiClient 인터셉터에서 로깅됨
    }
  };

  // 부서 일괄 추가 핸들러
  const handleBatchAddDept = async (deptId: string) => {
    if (checkedUserIds.size === 0) {
      await showAlert('선택 필요', '부서를 추가할 사용자를 먼저 선택해주세요.', '확인');
      return;
    }

    setIsBatchProcessing(true);
    setIsDeptDropdownOpen(false);

    try {
      const checkedUsers = users.filter((u) => checkedUserIds.has(u.id));

      for (const user of checkedUsers) {
        const existingDeptIds = user.deptPermissions?.map((dp) => dp.deptId) || [];
        if (existingDeptIds.includes(deptId)) continue; // 이미 있으면 스킵
        await updateDeptPermissions(user.id, [...existingDeptIds, deptId]);
      }

      setCheckedUserIds(new Set());
      onRefreshUsers?.();
    } catch {
      await showAlert('부서 추가 실패', '부서 일괄 추가 중 오류가 발생했습니다.', '확인');
    } finally {
      setIsBatchProcessing(false);
    }
  };

  const handleDeptDropdownToggle = async () => {
    if (!isDeptDropdownOpen && departments.length === 0) {
      try {
        const data = await getAdminDepartments();
        setDepartments(data);
      } catch {
        // apiClient 인터셉터에서 로깅됨
      }
    }
    setIsDeptDropdownOpen(!isDeptDropdownOpen);
  };

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (deptDropdownRef.current && !deptDropdownRef.current.contains(e.target as Node)) {
        setIsDeptDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div style={{ flex: 1, padding: '0 20px 19px', overflowY: 'auto' }}>
      <div style={{ padding: '19px 20px 0 20px' }}>
        <h2 style={{ ...adminTitleStyle, margin: '0 0 33px 0' }}>
          사용자 목록
        </h2>
        <div style={{ position: 'relative', marginBottom: '16px', maxWidth: '372px' }}>
          <SearchIcon
            width={20}
            height={20}
            style={{
              position: 'absolute',
              left: '14px',
              top: '50%',
              transform: 'translateY(-50%)',
              pointerEvents: 'none',
              color: 'var(--color-grayscale-400)',
            }}
          />
          <input
            type="text"
            placeholder="이름, 이메일, 부서 검색"
            value={searchQuery}
            onChange={(e) => { setSearchQuery(e.target.value); onSearch?.(e.target.value); }}
            style={{
              width: '100%',
              padding: '10px 16px 10px 44px',
              borderRadius: '8px',
              border: '1px solid var(--color-grayscale-200)',
              backgroundColor: 'var(--color-grayscale-50)',

              fontSize: '16px',
              fontWeight: '400',
              color: 'var(--color-grayscale-900)',
              outline: 'none',
              boxSizing: 'border-box',
            }}
          />
        </div>
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
            {/* 액션바 */}
            <div style={{
              margin: '0 20px 8px',
              padding: '12px 20px',
              borderBottom: '1px solid var(--color-primary-400, #B4BDFA)',
              backgroundColor: 'var(--color-primary-100, #F2F3FF)',
              display: 'flex',
              alignItems: 'center',
              gap: '16px',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
                <Checkbox
                  checked={allChecked}
                  onChange={handleToggleAll}
                />
                <span style={{
                  fontSize: '14px',
                  fontWeight: '500',
                  color: 'var(--color-grayscale-900)',
                }}>
                  {checkedUserIds.size > 0 ? `${checkedUserIds.size}명 선택됨` : '전체 선택'}
                </span>
              </div>

              <div style={{
                width: '1px',
                height: '20px',
                backgroundColor: 'var(--color-primary-400, #B4BDFA)',
              }} />

              {/* 부서 일괄 추가 */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <img src={deptAdd2Icon} alt="" style={{ width: '18px', height: '18px' }} />
                <span style={{
                  fontSize: '14px',
                  fontWeight: '500',
                  color: 'var(--color-primary-600)',
                }}>
                  부서 일괄 추가
                </span>
                <div ref={deptDropdownRef} style={{ position: 'relative' }}>
                  <button
                    type="button"
                    onClick={handleDeptDropdownToggle}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      padding: '6px 14px',
                      borderRadius: '8px',
                      border: '1px solid var(--color-grayscale-200)',
                      backgroundColor: 'var(--color-grayscale-50)',
        
                      fontSize: '14px',
                      fontWeight: '400',
                      color: 'var(--color-grayscale-900)',
                      cursor: 'pointer',
                    }}
                  >
                    부서 선택
                    <span style={{ fontSize: '16px', color: 'var(--color-grayscale-500)' }}>+</span>
                  </button>

                  {isDeptDropdownOpen && (
                    <div style={{
                      position: 'absolute',
                      top: '100%',
                      left: 0,
                      marginTop: '4px',
                      width: '200px',
                      maxHeight: '240px',
                      overflowY: 'auto',
                      backgroundColor: 'var(--color-grayscale-50)',
                      borderRadius: '8px',
                      boxShadow: 'var(--shadow-dropdown)',
                      border: '1px solid var(--color-grayscale-150)',
                      zIndex: 100,
                    }}>
                      {departments.map((dept) => (
                        <div
                          key={dept.id}
                          onClick={() => handleBatchAddDept(dept.id)}
                          style={{
                            padding: '10px 16px',
                            fontSize: '14px',
                            color: 'var(--color-grayscale-900)',
                            cursor: isBatchProcessing ? 'wait' : 'pointer',
                            transition: 'background-color 0.15s',
                            opacity: isBatchProcessing ? 0.5 : 1,
                          }}
                          onMouseOver={(e) => {
                            if (!isBatchProcessing) e.currentTarget.style.backgroundColor = 'var(--color-grayscale-100)';
                          }}
                          onMouseOut={(e) => {
                            e.currentTarget.style.backgroundColor = 'transparent';
                          }}
                        >
                          {dept.deptName}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div style={{ overflowX: 'auto', padding: '0 20px' }}>
              <table style={adminTableStyle}>
                <thead>
                <tr style={{ height: '36px' }}>
                    <th style={{ ...adminHeaderCellStyle, width: '50px', borderTopLeftRadius: '10px' }}>
                      <Checkbox
                        checked={allChecked}
                        onChange={handleToggleAll}
                      />
                    </th>
                    <th style={{ ...adminHeaderCellStyle, textAlign: 'left', width: '200px' }}>이름 / 이메일</th>
                    <th style={adminHeaderCellStyle}>소속 부서</th>
                    <th style={{ ...adminHeaderCellStyle, width: '120px' }}>직급</th>
                    <th style={{ ...adminHeaderCellStyle, width: '120px' }}>가입일</th>
                    <th style={{ ...adminHeaderCellStyle, borderTopRightRadius: '10px', width: '160px' }}>권한</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((userItem) => {
                    const isChecked = checkedUserIds.has(userItem.id);
                    return (
                    <tr
                      key={userItem.id}
                      style={{
                        backgroundColor: isChecked ? 'var(--color-primary-50)' : 'transparent',
                        boxShadow: isChecked ? 'inset 0 -1px 0 rgba(98, 107, 247, 0.2)' : 'none',
                        transition: 'background-color 0.2s',
                      }}
                    >
                      <td style={{ ...adminCellStyle, textAlign: 'center' }}>
                        <Checkbox
                          checked={isChecked}
                          onChange={() => handleToggleUser(userItem.id)}
                        />
                      </td>
                      <td style={adminCellStyle}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                          <div style={{
                            width: '32px',
                            height: '32px',
                            borderRadius: '50%',
                            backgroundColor: getAvatarBgColor(userItem.name),
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontSize: '13px',
                            fontWeight: '600',
                            color: 'var(--color-grayscale-900)',
                            flexShrink: 0,
                          }}>
                            {userItem.name.charAt(0)}
                          </div>
                          <div>
                            <div style={{ color: 'var(--color-grayscale-900)', fontWeight: '500' }}>
                              {userItem.name}
                            </div>
                            <div style={{ color: 'var(--color-grayscale-500)', fontSize: '12px', marginTop: '2px' }}>
                              {userItem.email}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td style={adminCellStyle}>
                        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'center' }}>
                          {userItem.department && (
                            <span style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                              padding: '4px 8px',
                              borderRadius: '4px',
                              border: '1px solid var(--color-secondary-300)',
                              backgroundColor: 'var(--color-secondary-50)',
                
                              fontSize: '11px',
                              fontWeight: '500',
                              lineHeight: '16px',
                              color: 'var(--color-grayscale-900)',
                            }}>
                              {userItem.department}
                            </span>
                          )}
                          {userItem.deptPermissions?.map((dp) => (
                            <span
                              key={dp.id}
                              style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '4px',
                                padding: '4px 8px',
                                borderRadius: '4px',
                                border: '1px solid var(--color-tertiary-200)',
                                backgroundColor: 'var(--color-tertiary-50)',
                  
                                fontSize: '11px',
                                fontWeight: '500',
                                lineHeight: '16px',
                                color: 'var(--color-grayscale-900)',
                              }}
                            >
                              {dp.deptName}
                            </span>
                          ))}
                          <button
                            type="button"
                            onClick={() => { setSelectedUserId(userItem.id); setIsDeptModalOpen(true); }}
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                              padding: '4px 8px',
                              borderRadius: '4px',
                              border: '1px dashed var(--color-grayscale-200)',
                              backgroundColor: 'var(--color-grayscale-50)',
                
                              fontSize: '11px',
                              fontWeight: '500',
                              lineHeight: '16px',
                              color: 'var(--color-grayscale-400)',
                              cursor: 'pointer',
                            }}
                          >
                            추가
                            <img src={deptAddIcon} alt="추가" style={{ width: '10px', height: '10px' }} />
                          </button>
                        </div>
                      </td>
                      <td style={{ ...adminCellStyle, textAlign: 'center', color: userItem.jobTitle ? 'var(--color-grayscale-900)' : 'var(--color-grayscale-500)' }}>
                        {userItem.jobTitle || '-'}
                      </td>
                      <td style={{ ...adminCellStyle, color: 'var(--color-grayscale-500)', textAlign: 'center' }}>
                        {new Date(userItem.createdAt).toLocaleDateString('en-CA', {
                          year: 'numeric',
                          month: '2-digit',
                          day: '2-digit'
                        })}
                      </td>
                      <td style={adminCellStyle}>
                        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                          {userItem.authorities.map((authority) => (
                            <span
                              key={authority}
                              style={{
                                padding: '4px 10px',
                                backgroundColor: authority === 'ADMIN' ? 'var(--color-badge-admin-bg)' : 'var(--color-badge-default-bg)',
                                color: authority === 'ADMIN' ? 'var(--color-badge-admin-text)' : 'var(--color-badge-default-text)',
                                borderRadius: '12px',
                                fontSize: '12px',
                                fontWeight: '500',
                              }}
                            >
                              {authority}
                            </span>
                          ))}
                        </div>
                      </td>
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

      <DeptAddModal
        isOpen={isDeptModalOpen}
        onClose={() => setIsDeptModalOpen(false)}
        onConfirm={handleDeptConfirm}
        existingDeptIds={selectedUser?.deptPermissions?.map((dp) => dp.deptId) || []}
      />
    </div>
  );
}

export default AdminUserManagement;

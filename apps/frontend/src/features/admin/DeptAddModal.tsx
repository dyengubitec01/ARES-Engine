// created by ARES team [2026-04-01]
import { useEffect, useState } from 'react';
import { Department, getAdminDepartments } from '../../services/admin.service';
import {
  GRADIENT,
  GRADIENT_ACTIVE_SHADOW,
  secondaryButtonStyle,
  secondaryButtonHoverHandlers,
} from '../../styles/buttonStyles';
import { useScrollFade } from '../../hooks/useScrollFade';

interface DeptAddModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (selectedDeptIds: string[]) => void;
  existingDeptIds?: string[];
}

function DeptAddModal({ isOpen, onClose, onConfirm, existingDeptIds = [] }: DeptAddModalProps) {
  const [departments, setDepartments] = useState<Department[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const { ref: scrollContainerRef, showTopFade, showBottomFade, handleScroll } = useScrollFade<HTMLDivElement>();

  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
      setSelectedIds(new Set(existingDeptIds));
      fetchDepartments();
    } else {
      document.body.style.overflow = 'unset';
      setSearchQuery('');
      setSelectedIds(new Set());
    }
    return () => {
      document.body.style.overflow = 'unset';
    };
    // 모달 오픈 시점의 existingDeptIds로 초기화 의도 (사용자 작업 중인 선택 덮어쓰기 방지)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  const fetchDepartments = async () => {
    setIsLoading(true);
    try {
      const data = await getAdminDepartments();
      setDepartments(data);
    } catch {
      // apiClient 인터셉터에서 로깅됨
    } finally {
      setIsLoading(false);
    }
  };

  const filteredDepartments = departments.filter((dept) =>
    dept.deptName.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 10000,
        padding: '20px',
      }}
      onClick={onClose}
    >
      <div
        style={{
          backgroundColor: 'var(--color-grayscale-50)',
          borderRadius: '16px',
          boxShadow: 'var(--shadow-modal)',
          width: '688px',
          maxHeight: '80vh',
          padding: '40px',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: 'center',
          gap: '36px',
          animation: 'modalFadeIn 0.2s ease-out',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* 헤더 */}
        <div style={{ textAlign: 'left', width: '100%' }}>
          <h2 style={{
            margin: 0,
            color: 'var(--color-grayscale-900)',

            fontSize: '24px',
            fontStyle: 'normal',
            fontWeight: '600',
          }}>
            부서 일괄 추가
          </h2>
          <p style={{
            margin: '4px 0 0 0',

            fontSize: '14px',
            fontStyle: 'normal',
            fontWeight: '400',
            color: 'var(--color-grayscale-500)',
          }}>
            선택된 직원에게 파견 부서를 추가합니다
          </p>
        </div>

        {/* 검색 */}
        <div style={{
          position: 'relative',
          width: '100%',
        }}>
          <svg
            width="18"
            height="18"
            viewBox="0 0 18 18"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            style={{
              position: 'absolute',
              left: '16px',
              top: '50%',
              transform: 'translateY(-50%)',
              pointerEvents: 'none',
            }}
          >
            <circle cx="8" cy="8" r="5.5" stroke="var(--color-grayscale-300)" strokeWidth="1.5" />
            <path d="M12.5 12.5L16 16" stroke="var(--color-grayscale-300)" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
          <input
            type="text"
            placeholder="부서 검색"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              width: '100%',
              padding: '12px 16px 12px 44px',
              border: '1px solid var(--color-grayscale-150)',
              borderRadius: '8px',
              fontSize: '14px',
  
              color: 'var(--color-grayscale-900)',
              outline: 'none',
              boxSizing: 'border-box',
              backgroundColor: 'var(--color-grayscale-50)',
            }}
          />
        </div>

        {/* 부서 목록 */}
        <div style={{ position: 'relative', width: '100%', height: '372px' }}>
          {showTopFade && (
            <div style={{
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              height: '24px',
              background: 'linear-gradient(to bottom, var(--color-grayscale-50), transparent)',
              pointerEvents: 'none',
              zIndex: 1,
            }} />
          )}
          {showBottomFade && (
            <div style={{
              position: 'absolute',
              bottom: 0,
              left: 0,
              right: 0,
              height: '24px',
              background: 'linear-gradient(to top, var(--color-grayscale-50), transparent)',
              pointerEvents: 'none',
              zIndex: 1,
            }} />
          )}
          <div ref={scrollContainerRef} onScroll={handleScroll} style={{
          width: '100%',
          height: '100%',
          overflowY: 'auto',
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: '10px',
          alignContent: 'start',
          paddingRight: '20px',
          boxSizing: 'border-box',
        }}>
          {isLoading ? (
            <div style={{
              gridColumn: '1 / -1',
              padding: '40px',
              textAlign: 'center',
              color: 'var(--color-grayscale-500)',
            }}>
              부서 목록을 불러오는 중...
            </div>
          ) : filteredDepartments.length === 0 ? (
            <div style={{
              gridColumn: '1 / -1',
              padding: '40px',
              textAlign: 'center',
              color: 'var(--color-grayscale-500)',
            }}>
              {searchQuery ? '검색 결과가 없습니다' : '등록된 부서가 없습니다'}
            </div>
          ) : (
            filteredDepartments.map((dept) => {
              const isSelected = selectedIds.has(dept.id);
              return (
                <button
                  key={dept.id}
                  type="button"
                  onClick={() => toggleSelect(dept.id)}
                  style={{
                    padding: '10px 16px',
                    borderRadius: '4px',
                    border: isSelected
                      ? '1px solid var(--color-primary-600)'
                      : '1px solid var(--color-grayscale-200)',
                    backgroundColor: isSelected
                      ? 'var(--color-primary-600)'
                      : 'var(--color-grayscale-100)',

                    fontSize: '16px',
                    fontWeight: '400',
                    lineHeight: '26px',
                    letterSpacing: '-0.32px',
                    color: isSelected ? '#FFF' : 'var(--color-grayscale-900)',
                    cursor: 'pointer',
                    textAlign: 'center',
                    transition: 'all 0.15s',
                  }}
                  onMouseOver={(e) => {
                    if (!isSelected) {
                      e.currentTarget.style.borderColor = 'var(--color-primary-600)';
                      e.currentTarget.style.backgroundColor = 'var(--color-primary-600-100)';
                      e.currentTarget.style.color = 'var(--color-primary-600)';
                    }
                  }}
                  onMouseOut={(e) => {
                    if (!isSelected) {
                      e.currentTarget.style.borderColor = 'var(--color-grayscale-200)';
                      e.currentTarget.style.backgroundColor = 'var(--color-grayscale-100)';
                      e.currentTarget.style.color = 'var(--color-grayscale-900)';
                    }
                  }}
                >
                  {dept.deptName}
                </button>
              );
            })
          )}
          </div>
        </div>

        {/* 하단 버튼 */}
        <div style={{
          display: 'flex',
          gap: '16px',
          width: '100%',
        }}>
          <button
            type="button"
            onClick={onClose}
            style={secondaryButtonStyle}
            {...secondaryButtonHoverHandlers}
          >
            닫기
          </button>
          <button
            type="button"
            onClick={() => onConfirm(Array.from(selectedIds))}
            style={{
              flex: 2,
              padding: '14px 24px',
              background: GRADIENT.primary,
              color: '#FFF',
              border: 'none',
              borderRadius: '999px',
              fontSize: '16px',
              fontWeight: '600',
  
              cursor: 'pointer',
              transition: 'all 0.2s',
            }}
            onMouseOver={(e) => {
              e.currentTarget.style.background = GRADIENT.primaryHover;
            }}
            onMouseOut={(e) => {
              e.currentTarget.style.background = GRADIENT.primarySoft;
              e.currentTarget.style.boxShadow = 'none';
            }}
            onMouseDown={(e) => {
              e.currentTarget.style.background = GRADIENT.primaryActive;
              e.currentTarget.style.boxShadow = GRADIENT_ACTIVE_SHADOW;
            }}
            onMouseUp={(e) => {
              e.currentTarget.style.background = GRADIENT.primaryHover;
              e.currentTarget.style.boxShadow = 'none';
            }}
          >
            추가하기
          </button>
        </div>
      </div>

      <style>
        {`
          @keyframes modalFadeIn {
            from {
              opacity: 0;
              transform: scale(0.95) translateY(-10px);
            }
            to {
              opacity: 1;
              transform: scale(1) translateY(0);
            }
          }
        `}
      </style>
    </div>
  );
}

export default DeptAddModal;

// created by ARES team [2026-04-06]
import Skeleton from './Skeleton';

interface TableSkeletonProps {
  headerHeight?: string;
  bodyHeight?: string;
}

function TableSkeleton({
  headerHeight = '36px',
  bodyHeight = '400px',
}: TableSkeletonProps) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      <Skeleton width="100%" height={headerHeight} borderRadius="8px" />
      <Skeleton width="100%" height={bodyHeight} borderRadius="8px" />
    </div>
  );
}

export default TableSkeleton;

// created by ARES team [2026-04-06]

interface SkeletonProps {
  width?: string | number;
  height?: string | number;
  borderRadius?: string;
  style?: React.CSSProperties;
}

function Skeleton({
  width = '100%',
  height = '16px',
  borderRadius = '4px',
  style
}: SkeletonProps) {
  return (
    <div
      style={{
        width,
        height,
        borderRadius,
        background: `linear-gradient(90deg, var(--skeleton-base) 25%, var(--skeleton-highlight) 50%, var(--skeleton-base) 75%)`,
        backgroundSize: '200% 100%',
        animation: 'shimmer 2s ease-in-out infinite',
        ...style,
      }}
    />
  );
}

export default Skeleton;

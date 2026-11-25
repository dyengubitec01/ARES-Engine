import { ReactNode } from 'react';

interface SidebarShellProps {
  profile: ReactNode;
  children: ReactNode;
}

function SidebarShell({ profile, children }: SidebarShellProps) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {children}
      {profile}
    </div>
  );
}

export default SidebarShell;

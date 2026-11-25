import { useNavigate } from 'react-router-dom';
import { useAppSidebar } from '../components/AppSidebar';
import PageLayout from '../layouts/PageLayout';
import DocumentApprovalList from '../features/documents/DocumentApprovalList';

function DocumentApprovalPage() {
  const navigate = useNavigate();

  const handleNewChat = async (): Promise<void> => {
    navigate('/chat');
  };

  const sidebar = useAppSidebar({
    activeRoomId: undefined,
    onNewChat: handleNewChat,
  });

  return (
    <PageLayout
      showSidebarToggle={true}
      sidebarContent={sidebar.sidebarContent}
      sidebarHeaderActions={sidebar.headerActions}
      sidebarHeaderTrailingActions={sidebar.headerTrailingActions}
      sidebarActions={sidebar.sidebarActions}
    >
      <DocumentApprovalList />
    </PageLayout>
  );
}

export default DocumentApprovalPage;

import { Outlet } from 'react-router-dom';
import AppSidebar from './AppSidebar';
import EmergencyBanner from './EmergencyBanner';

export default function DashboardLayout() {
  return (
    <div className="min-h-screen bg-background flex flex-col">
      <EmergencyBanner />
      <div className="flex flex-1">
        <AppSidebar />
        <main className="flex-1 p-8 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

import { useState, useEffect } from 'react';
import { Outlet } from 'react-router-dom';
import { TopHeader } from './TopHeader';
import { LeftSidebar } from './LeftSidebar';
import { FloatingActionButton } from './FloatingActionButton';
import { NotificationPanel } from './NotificationPanel';
import { VoiceCommandPanel } from './VoiceCommandPanel';
import { PinOverlay } from '@/components/overlays/PinOverlay';
import { PickupLoadingOverlay } from '@/components/overlays/PickupLoadingOverlay';
import { useRobotStore } from '@/stores/robotStore';

export function RobotLayout() {
  const [voicePanelOpen, setVoicePanelOpen] = useState(false);
  const { notificationPanelOpen, toggleNotificationPanel, sessionState, incrementSessionTime, decrementRemainingTime } = useRobotStore();

  // Global session timer
  useEffect(() => {
    if (sessionState !== 'ACTIVE') return;
    
    const interval = setInterval(() => {
      incrementSessionTime();
      decrementRemainingTime();
    }, 1000);
    
    return () => clearInterval(interval);
  }, [sessionState, incrementSessionTime, decrementRemainingTime]);

  // Close voice panel when notification panel opens
  useEffect(() => {
    if (notificationPanelOpen && voicePanelOpen) {
      setVoicePanelOpen(false);
    }
  }, [notificationPanelOpen]);

  const handleOpenVoice = () => {
    if (notificationPanelOpen) toggleNotificationPanel();
    setVoicePanelOpen(true);
  };

  return (
    <div className="min-h-screen bg-background">
      <TopHeader />
      <LeftSidebar />
      
      <main className="ml-20 mt-14 p-8 overflow-y-auto h-[calc(100vh-3.5rem)] hide-scrollbar">
        <Outlet />
      </main>
      
      <FloatingActionButton onVoiceOpen={handleOpenVoice} />
      <NotificationPanel />
      <VoiceCommandPanel open={voicePanelOpen} onClose={() => setVoicePanelOpen(false)} />
      <PinOverlay />
      <PickupLoadingOverlay />
    </div>
  );
}

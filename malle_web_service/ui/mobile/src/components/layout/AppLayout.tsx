import { ReactNode, useState, useEffect } from 'react';
import { Header } from './Header';
import { StatusBar } from './StatusBar';
import { BottomNav } from './BottomNav';
import { SearchOverlay } from '../search/SearchOverlay';
import { ProfileSheet } from '../profile/ProfileSheet';
import { VoiceCommandPanel } from '../voice/VoiceCommandPanel';
import { useAppStore } from '@/store/appStore';

interface AppLayoutProps {
  children: ReactNode;
}

export function AppLayout({ children }: AppLayoutProps) {
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [isVoiceOpen, setIsVoiceOpen] = useState(false);
  const { sessionState, session, taskMission, tickTimer, tickApproachingEta } = useAppStore();

  const isActive = sessionState === 'ACTIVE';
  const isApproaching = sessionState === 'APPROACHING';
  const isTaskMode = session.type === 'TASK' && !!taskMission;

  // Global countdown timer
  useEffect(() => {
    if (!isActive || isTaskMode) return;
    const interval = setInterval(() => tickTimer(), 1000);
    return () => clearInterval(interval);
  }, [isActive, isTaskMode, tickTimer]);

  // Global approaching ETA countdown
  useEffect(() => {
    if (!isApproaching) return;
    const interval = setInterval(() => tickApproachingEta(), 1000);
    return () => clearInterval(interval);
  }, [isApproaching, tickApproachingEta]);

  return (
    <div className="min-h-screen bg-background flex flex-col max-w-[430px] mx-auto relative">
      <Header 
        onSearchClick={() => setIsSearchOpen(true)} 
        onProfileClick={() => setIsProfileOpen(true)} 
      />
      <StatusBar />
      
      <main className="flex-1 overflow-y-auto px-5 py-6 space-y-5 pb-28 hide-scrollbar">
        {children}
      </main>

      <BottomNav />

      {/* Voice Command FAB — bottom-right, above nav */}
      <button
        onClick={() => setIsVoiceOpen(true)}
        className="fixed bottom-[118px] right-5 z-30 w-14 h-14 rounded-full bg-card/90 dark:bg-card/90 backdrop-blur-xl border border-border/50 shadow-xl ring-2 ring-primary/20 flex items-center justify-center transition-all duration-300 hover:shadow-2xl hover:scale-105 active:scale-90"
        title="Voice Command"
      >
        <span className="material-icons-round text-primary text-2xl">mic</span>
      </button>

      <SearchOverlay isOpen={isSearchOpen} onClose={() => setIsSearchOpen(false)} />
      <ProfileSheet isOpen={isProfileOpen} onClose={() => setIsProfileOpen(false)} />
      <VoiceCommandPanel open={isVoiceOpen} onClose={() => setIsVoiceOpen(false)} />
    </div>
  );
}

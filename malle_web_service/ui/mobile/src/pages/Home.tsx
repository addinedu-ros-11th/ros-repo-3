import { useState, useEffect } from 'react';
import { useAppStore } from '@/store/appStore';
// Timer is now managed globally in AppLayout
import { SessionStartCard } from '@/components/home/SessionStartCard';
import { ActiveSessionCard } from '@/components/home/ActiveSessionCard';
import { TaskActiveCard } from '@/components/home/TaskActiveCard';
import { LockboxCapacityCard } from '@/components/home/LockboxCapacityCard';
import { ShoppingListCard } from '@/components/home/ShoppingListCard';
import { ControlModeCard } from '@/components/home/ControlModeCard';
import { FindRobotBar } from '@/components/home/FindRobotBar';
import { StartSessionModal } from '@/components/home/StartSessionModal';
import { PinMatchingModal } from '@/components/home/PinMatchingModal';
import { RobotApproachingCard } from '@/components/home/RobotApproachingCard';

export default function Home() {
  const { userName, sessionState, session, taskMission, startGuide } = useAppStore();
  const [isStartModalOpen, setIsStartModalOpen] = useState(false);

  const isActive = sessionState === 'ACTIVE';
  const isApproaching = sessionState === 'APPROACHING' || sessionState === 'FINDING_ROBOT';
  const isPinMatching = sessionState === 'PIN_MATCHING';
  const isTaskMode = session.type === 'TASK' && !!taskMission;

  // Auto-start guide for Task/Guide when session becomes ACTIVE
  useEffect(() => {
    if (isActive && isTaskMode && taskMission?.type === 'GUIDE') {
      startGuide();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isActive]);

  return (
    <div className="space-y-5">
      {/* Greeting */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-foreground">
          Hello, {userName} <span className="inline-block animate-wave">👋</span>
        </h1>
        <p className="text-muted-foreground text-sm mt-1">
          {isActive 
            ? (isTaskMode ? "Task mission in progress." : "Your shopping session is active.")
            : "Your shopping assistant is ready."}
        </p>
      </div>

      {/* Content based on session state */}
      {!isActive && !isApproaching && !isPinMatching && (
        <SessionStartCard onStart={() => setIsStartModalOpen(true)} />
      )}

      {isApproaching && (
        <RobotApproachingCard />
      )}

      {isActive && (
        <>
          {isTaskMode ? (
            <TaskActiveCard />
          ) : (
            <>
              <ActiveSessionCard />
              
              <div className="grid grid-cols-2 gap-4">
                <LockboxCapacityCard />
                <ShoppingListCard />
              </div>

              <ControlModeCard />
              <FindRobotBar />
            </>
          )}
        </>
      )}

      {/* Modals */}
      <StartSessionModal 
        isOpen={isStartModalOpen} 
        onClose={() => setIsStartModalOpen(false)} 
      />
      
      <PinMatchingModal 
        isOpen={isPinMatching} 
      />
    </div>
  );
}

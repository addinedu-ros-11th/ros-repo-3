import { useState } from 'react';
import { useRobotStore } from '@/stores/robotStore';

interface FloatingActionButtonProps {
  onVoiceOpen: () => void;
}

export function FloatingActionButton({ onVoiceOpen }: FloatingActionButtonProps) {
  const [expanded, setExpanded] = useState(false);
  const [showEmergencyOverlay, setShowEmergencyOverlay] = useState(false);
  const [showReturnOverlay, setShowReturnOverlay] = useState(false);
  const { sessionState, robot, setRobotStatus, endSession } = useRobotStore();

  if (sessionState !== 'ACTIVE') return null;

  const isPaused = robot.status === 'STOPPED';

  const handlePauseResume = () => {
    setRobotStatus(isPaused ? 'MOVING' : 'STOPPED');
    setExpanded(false);
  };

  const handleReturnToStation = () => {
    setShowReturnOverlay(true);
    setExpanded(false);
  };

  const confirmReturn = () => {
    endSession();
    setShowReturnOverlay(false);
  };

  const handleEmergencyStop = () => {
    setRobotStatus('STOPPED');
    setShowEmergencyOverlay(true);
    setExpanded(false);
  };

  const handleResume = () => {
    setRobotStatus('MOVING');
    setShowEmergencyOverlay(false);
  };

  return (
    <>
      {/* FAB Stack — single column, center-aligned circles */}
      <div className="fixed bottom-8 right-8 z-40 flex flex-col items-center gap-3">
        {/* Voice Command Button — always visible, sits at top */}
        <button
          onClick={onVoiceOpen}
          className="w-14 h-14 rounded-full bg-white/90 dark:bg-slate-800/90 backdrop-blur-xl border border-border/50 shadow-xl ring-2 ring-primary/20 flex items-center justify-center transition-all duration-300 hover:shadow-2xl hover:scale-105 active:scale-90 group relative"
          title="Voice Command"
        >
          <span className="material-icons-round text-primary dark:text-blue-400 text-2xl">mic</span>
          <span className="absolute right-16 opacity-0 group-hover:opacity-100 transition-opacity text-xs font-bold bg-slate-800 text-white px-3 py-1.5 rounded-lg shadow-lg whitespace-nowrap pointer-events-none">
            Voice Command
          </span>
        </button>

        {/* Expanded actions */}
        {expanded && (
          <>
            {/* Emergency Stop */}
            <div className="relative flex items-center justify-center animate-fade-in" style={{ animationDelay: '0.1s' }}>
              <span className="absolute right-14 text-xs font-bold bg-slate-800 text-white px-3 py-1.5 rounded-lg shadow-lg whitespace-nowrap">
                Emergency Stop
              </span>
              <button onClick={handleEmergencyStop} className="w-12 h-12 rounded-full bg-red-500 text-white shadow-lg flex items-center justify-center active:scale-95 transition-all">
                <span className="material-icons-round">emergency</span>
              </button>
            </div>

            {/* Return to Station */}
            <div className="relative flex items-center justify-center animate-fade-in" style={{ animationDelay: '0.05s' }}>
              <span className="absolute right-14 text-xs font-bold bg-slate-800 text-white px-3 py-1.5 rounded-lg shadow-lg whitespace-nowrap">
                Return to Station
              </span>
              <button onClick={handleReturnToStation} className="w-12 h-12 rounded-full bg-primary text-white shadow-lg flex items-center justify-center active:scale-95 transition-all">
                <span className="material-icons-round">home</span>
              </button>
            </div>

            {/* Pause/Resume */}
            <div className="relative flex items-center justify-center animate-fade-in">
              <span className="absolute right-14 text-xs font-bold bg-slate-800 text-white px-3 py-1.5 rounded-lg shadow-lg whitespace-nowrap">
                {isPaused ? 'Resume' : 'Pause'}
              </span>
              <button onClick={handlePauseResume} className="w-12 h-12 rounded-full bg-amber-500 text-white shadow-lg flex items-center justify-center active:scale-95 transition-all">
                <span className="material-icons-round">{isPaused ? 'play_arrow' : 'pause'}</span>
              </button>
            </div>
          </>
        )}

        {/* Main FAB */}
        <button onClick={() => setExpanded(!expanded)} className="w-14 h-14 rounded-full bg-slate-900 dark:bg-white text-white dark:text-slate-900 shadow-2xl flex items-center justify-center active:scale-95 transition-all">
          <span className="material-icons-round text-2xl transition-transform duration-200" style={{ transform: expanded ? 'rotate(45deg)' : 'rotate(0deg)' }}>
            {expanded ? 'close' : 'more_vert'}
          </span>
        </button>
      </div>

      {/* Emergency Stop Overlay */}
      {showEmergencyOverlay && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center">
          <div className="overlay-card w-[480px] text-center">
            <div className="w-20 h-20 rounded-full bg-red-100 dark:bg-red-900/30 mx-auto mb-6 flex items-center justify-center">
              <span className="material-icons-round text-red-500 text-4xl">emergency</span>
            </div>
            <h2 className="text-2xl font-bold text-foreground mb-2">Emergency Stop Activated</h2>
            <p className="text-sm text-muted-foreground mb-8">The robot has been stopped. Press Resume to continue operations.</p>
            <button onClick={handleResume} className="btn-primary w-full py-4 text-lg">
              <span className="material-icons-round mr-2 align-middle">play_arrow</span>
              Resume
            </button>
          </div>
        </div>
      )}

      {/* Return to Station Overlay */}
      {showReturnOverlay && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center">
          <div className="overlay-card w-[480px] text-center">
            <div className="w-20 h-20 rounded-full bg-primary/10 mx-auto mb-6 flex items-center justify-center">
              <span className="material-icons-round text-primary text-4xl">home</span>
            </div>
            <h2 className="text-2xl font-bold text-foreground mb-2">Return to Station</h2>
            <p className="text-sm text-muted-foreground mb-8">로봇을 스테이션으로 복귀시킬까요?</p>
            <div className="flex space-x-3">
              <button onClick={() => setShowReturnOverlay(false)} className="btn-secondary flex-1 py-4 text-lg">
                Cancel
              </button>
              <button onClick={confirmReturn} className="btn-primary flex-1 py-4 text-lg">
                Confirm
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

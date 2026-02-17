import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppStore, RobotMode } from '@/store/appStore';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';

const modes: { id: RobotMode; label: string; icon: string; description: string }[] = [
  { id: 'GUIDE', label: 'Guide', icon: 'alt_route', description: '목적지까지 로봇이 안내합니다' },
  { id: 'FOLLOW', label: 'Follow Me', icon: 'directions_run', description: '로봇이 당신을 따라갑니다' },
  { id: 'PICKUP', label: 'Pickup', icon: 'shopping_bag', description: '로봇이 물건을 가져옵니다' },
];

const modeColors = {
  GUIDE: 'from-blue-500 to-indigo-600',
  FOLLOW: 'from-emerald-500 to-teal-600',
  PICKUP: 'from-orange-500 to-amber-600',
};

const modeLabels: Record<RobotMode, string> = {
  GUIDE: 'Guide',
  FOLLOW: 'Follow Me',
  PICKUP: 'Pickup',
};

export default function Mode() {
  const navigate = useNavigate();
  const { robot, setRobotMode, sessionState, session, taskMission, pickupOrder } = useAppStore();
  const currentMode = robot?.mode;
  const isActive = sessionState === 'ACTIVE';
  const isTaskMode = isActive && session.type === 'TASK' && !!taskMission;
  const [switchTarget, setSwitchTarget] = useState<RobotMode | null>(null);

  // Pickup is in progress if order exists and not IDLE/DONE
  const isPickupInProgress = !!pickupOrder && pickupOrder.status !== 'IDLE' && pickupOrder.status !== 'DONE';

  const isModeDisabled = (modeId: RobotMode) => {
    if (!isActive) return true;
    if (isPickupInProgress && modeId !== 'PICKUP') return true;
    if (!isTaskMode) return false;
    if (modeId === 'FOLLOW') return true;
    if (taskMission?.type === 'GUIDE' && modeId !== 'GUIDE') return true;
    if (taskMission?.type === 'PICKUP' && modeId !== 'PICKUP') return true;
    return false;
  };

  const getDisabledReason = (modeId: RobotMode) => {
    if (!isActive) return null;
    if (isPickupInProgress && modeId !== 'PICKUP') return '픽업 미션 진행 중';
    if (modeId === 'FOLLOW' && isTaskMode) return 'Time 모드에서만 사용 가능';
    if (isTaskMode && isModeDisabled(modeId)) return 'Task 미션과 관련 없는 모드';
    return null;
  };

  const handleModeSelect = (mode: RobotMode) => {
    if (!isActive || isModeDisabled(mode)) return;
    // Allow re-entering the current mode page
    if (mode === currentMode) {
      navigate(`/mode/${mode.toLowerCase()}`);
      return;
    }
    // Guide/Follow ↔ Guide/Follow/Pickup switching: show confirmation
    if (currentMode && (currentMode === 'GUIDE' || currentMode === 'FOLLOW')) {
      setSwitchTarget(mode);
      return;
    }
    setRobotMode(mode);
    navigate(`/mode/${mode?.toLowerCase()}`);
  };

  const confirmSwitch = () => {
    if (!switchTarget) return;
    setRobotMode(switchTarget);
    navigate(`/mode/${switchTarget.toLowerCase()}`);
    setSwitchTarget(null);
  };

  return (
    <div className="space-y-5">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-foreground">Control Mode</h1>
        <p className="text-muted-foreground text-sm mt-1">
          {isActive 
            ? (isTaskMode ? 'Task mission mode — limited to assigned mission' : 'Select a mode for your robot')
            : 'Start a session to control the robot'}
        </p>
      </div>

      {/* Mode Cards */}
      <div className="space-y-4">
        {modes.map((mode) => {
          const disabled = isModeDisabled(mode.id);
          const reason = getDisabledReason(mode.id);

          return (
            <div key={mode.id}>
              <button
                onClick={() => handleModeSelect(mode.id)}
                disabled={disabled}
                className={`w-full bg-gradient-to-br ${modeColors[mode.id!]} rounded-3xl p-6 relative overflow-hidden text-left transition-all active-press disabled:opacity-40 disabled:cursor-not-allowed ${
                  currentMode === mode.id ? 'ring-4 ring-white/50 scale-[1.02]' : ''
                }`}
              >
                {/* Decoration */}
                <div className="card-decoration -right-10 -top-10 w-40 h-40 bg-white/20" />
                <div className="card-decoration -left-6 -bottom-6 w-24 h-24 bg-white/10" />

                <div className="relative z-10 flex items-center gap-5">
                  <div className="w-16 h-16 rounded-2xl bg-white/20 backdrop-blur-sm flex items-center justify-center">
                    <span className="material-icons-round text-white text-3xl">{mode.icon}</span>
                  </div>
                  <div className="flex-1">
                    <h2 className="text-xl font-bold text-white">{mode.label}</h2>
                    <p className="text-white/70 text-sm mt-1">{mode.description}</p>
                  </div>
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                    currentMode === mode.id ? 'bg-white' : 'bg-white/20'
                  }`}>
                    <span className={`material-icons-round ${
                      currentMode === mode.id ? 'text-primary' : 'text-white'
                    }`}>
                      {currentMode === mode.id ? 'check' : 'arrow_forward'}
                    </span>
                  </div>
                </div>

                {currentMode === mode.id && (
                  <div className="mt-4 bg-white/10 backdrop-blur-sm rounded-xl px-4 py-2 inline-flex items-center gap-2">
                    <span className="w-2 h-2 bg-white rounded-full animate-pulse" />
                    <span className="text-white text-sm font-medium">Active</span>
                  </div>
                )}
              </button>

              {reason && (
                <p className="text-xs text-muted-foreground mt-1 ml-2 flex items-center gap-1">
                  <span className="material-icons-round text-xs">info</span>
                  {reason}
                </p>
              )}
            </div>
          );
        })}
      </div>

      {!isActive && (
        <div className="bg-muted rounded-2xl p-4 flex items-center gap-3">
          <span className="material-icons-round text-muted-foreground">info</span>
          <p className="text-sm text-muted-foreground">
            Start a session from the Home tab to use robot control modes
          </p>
        </div>
      )}
      {/* Mode Switch Confirmation */}
      <AlertDialog open={!!switchTarget} onOpenChange={(open) => !open && setSwitchTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Switch Mode</AlertDialogTitle>
            <AlertDialogDescription>
              {currentMode && switchTarget
                ? `Currently running ${modeLabels[currentMode]} mode. Would you like to switch to ${modeLabels[switchTarget]} mode?`
                : ''}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={confirmSwitch}>Switch</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

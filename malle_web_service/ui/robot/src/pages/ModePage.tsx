import { useRobotStore } from '@/stores/robotStore';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

type ModeType = 'GUIDE' | 'FOLLOW' | 'PICKUP';

interface ModeCardProps {
  mode: ModeType;
  icon: string;
  title: string;
  description: string;
  gradient: string;
  isActive: boolean;
  onStart: () => void;
  onStop: () => void;
}

function ModeCard({ mode, icon, title, description, gradient, isActive, onStart, onStop }: ModeCardProps) {
  return (
    <div className={`robot-card h-56 flex flex-col justify-between ${gradient}`}>
      <div className="absolute -right-8 -top-8 w-40 h-40 bg-white/10 rounded-full blur-2xl" />
      <div className="relative z-10">
        <div className="flex items-center justify-between mb-4">
          <span className="material-icons-round text-4xl text-white/90">{icon}</span>
          <span className={isActive ? 'mode-pill-on' : 'mode-pill-off'}>
            {isActive ? 'ON' : 'OFF'}
          </span>
        </div>
        <h3 className="text-2xl font-bold text-white">{title}</h3>
        <p className="text-sm text-white/80">{description}</p>
      </div>
      <div className="relative z-10">
        {isActive ? (
          <button onClick={onStop} className="w-full btn-secondary bg-white/20 border-white/30 text-white hover:bg-white/30">
            Stop
          </button>
        ) : (
          <button onClick={onStart} className="w-full btn-secondary bg-white text-slate-800 hover:bg-white/90">
            Start
          </button>
        )}
      </div>
    </div>
  );
}

export function ModePage() {
  const { activeMode, setActiveMode, startFollow, stopFollow, guide, startGuide, stopGuide } = useRobotStore();
  const [showSwitchDialog, setShowSwitchDialog] = useState(false);
  const [pendingMode, setPendingMode] = useState<ModeType | null>(null);
  const navigate = useNavigate();

  const modeLabels: Record<ModeType, string> = {
    GUIDE: 'Guide',
    FOLLOW: 'Follow Me',
    PICKUP: 'Pickup',
  };

  const navigateToMode = (mode: ModeType) => {
    switch (mode) {
      case 'GUIDE': navigate('/mode/guide'); break;
      case 'FOLLOW': navigate('/mode/follow'); break;
      case 'PICKUP': navigate('/mode/pickup'); break;
    }
  };

  const handleModeStart = (mode: ModeType) => {
    if (activeMode && activeMode !== mode) {
      setPendingMode(mode);
      setShowSwitchDialog(true);
      return;
    }
    navigateToMode(mode);
  };

  const handleModeStop = () => {
    if (activeMode === 'FOLLOW') stopFollow();
    else if (activeMode === 'GUIDE') stopGuide();
    else setActiveMode(null);
  };

  const handleSwitchConfirm = () => {
    handleModeStop();
    setShowSwitchDialog(false);
    if (pendingMode) {
      navigateToMode(pendingMode);
      setPendingMode(null);
    }
  };

  return (
    <div>
      <h1 className="text-page-title mb-8">Select Mode</h1>

      <div className="grid grid-cols-3 gap-6">
        <ModeCard
          mode="GUIDE"
          icon="alt_route"
          title="Guide"
          description="Navigate to destinations"
          gradient="bg-gradient-to-br from-blue-500 to-blue-700"
          isActive={activeMode === 'GUIDE'}
          onStart={() => handleModeStart('GUIDE')}
          onStop={handleModeStop}
        />
        <ModeCard
          mode="FOLLOW"
          icon="directions_run"
          title="Follow Me"
          description="Follow the customer"
          gradient="bg-gradient-to-br from-purple-500 to-purple-700"
          isActive={activeMode === 'FOLLOW'}
          onStart={() => handleModeStart('FOLLOW')}
          onStop={handleModeStop}
        />
        <ModeCard
          mode="PICKUP"
          icon="shopping_bag"
          title="Pickup"
          description="Retrieve store orders"
          gradient="bg-gradient-to-br from-pink-500 to-pink-700"
          isActive={activeMode === 'PICKUP'}
          onStart={() => handleModeStart('PICKUP')}
          onStop={handleModeStop}
        />
      </div>

      {/* Switch Mode Dialog */}
      {showSwitchDialog && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center">
          <div className="bg-card rounded-2xl p-6 w-96 shadow-2xl animate-scale-in">
            <h3 className="text-lg font-bold text-foreground mb-2">Switch Mode?</h3>
            <p className="text-muted-foreground mb-6">
              현재 {modeLabels[activeMode!]} 모드 실행 중입니다. {pendingMode && modeLabels[pendingMode]} 모드로 변경할까요?
            </p>
            <div className="flex space-x-3">
              <button onClick={() => { setShowSwitchDialog(false); setPendingMode(null); }} className="flex-1 btn-secondary">
                Cancel
              </button>
              <button onClick={handleSwitchConfirm} className="flex-1 btn-primary">
                Switch
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

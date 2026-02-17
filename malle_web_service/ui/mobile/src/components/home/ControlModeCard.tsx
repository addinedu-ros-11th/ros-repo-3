import { useNavigate } from 'react-router-dom';
import { useAppStore, RobotMode } from '@/store/appStore';

const modes: { id: RobotMode; label: string; icon: string; path: string }[] = [
  { id: 'GUIDE', label: 'Guide', icon: 'near_me', path: '/mode/guide' },
  { id: 'FOLLOW', label: 'Follow Me', icon: 'directions_run', path: '/mode/follow' },
  { id: 'PICKUP', label: 'Pickup', icon: 'shopping_bag', path: '/mode/pickup' },
];

export function ControlModeCard() {
  const navigate = useNavigate();
  const { robot, setRobotMode } = useAppStore();
  const currentMode = robot?.mode;

  const handleModeSelect = (mode: RobotMode, path: string) => {
    setRobotMode(mode);
    navigate(path);
  };

  return (
    <div className="bg-muted dark:bg-secondary rounded-3xl p-5 border border-border">
      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        <span className="material-icons-round text-muted-foreground">tune</span>
        <h3 className="font-bold text-foreground">Control Mode</h3>
      </div>

      {/* Mode Grid */}
      <div className="grid grid-cols-3 gap-3">
        {modes.map((mode) => (
          <button
            key={mode.id}
            onClick={() => handleModeSelect(mode.id, mode.path)}
            className={`flex flex-col items-center p-4 rounded-2xl transition-all active-press ${
              currentMode === mode.id
                ? 'bg-primary text-primary-foreground shadow-md scale-105 ring-2 ring-primary ring-offset-2 ring-offset-background'
                : 'bg-card shadow-sm hover:bg-card/80'
            }`}
          >
            <div className={`w-10 h-10 rounded-full flex items-center justify-center mb-2 ${
              currentMode === mode.id
                ? 'bg-white/20'
                : 'bg-muted'
            }`}>
              <span className={`material-icons-round text-xl ${
                currentMode === mode.id ? 'text-white' : 'text-muted-foreground'
              }`}>
                {mode.icon}
              </span>
            </div>
            <span className={`text-xs font-semibold ${
              currentMode === mode.id ? 'text-white' : 'text-foreground'
            }`}>
              {mode.label}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

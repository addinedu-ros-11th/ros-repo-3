import { useAppStore } from '@/store/appStore';

export function StatusBar() {
  const { sessionState, robot, session } = useAppStore();

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const getModeIcon = () => {
    if (!robot?.mode) return 'remove';
    switch (robot.mode) {
      case 'GUIDE': return 'alt_route';
      case 'FOLLOW': return 'directions_run';
      case 'PICKUP': return 'shopping_bag';
      default: return 'remove';
    }
  };

  const getModeName = () => {
    if (!robot?.mode) return '—';
    switch (robot.mode) {
      case 'GUIDE': return 'Guide';
      case 'FOLLOW': return 'Follow Me';
      case 'PICKUP': return 'Pickup';
      default: return '—';
    }
  };

  const isActive = sessionState === 'ACTIVE';
  const isTaskMode = session.type === 'TASK';

  return (
    <div className="bg-muted/50 dark:bg-secondary/50 px-6 py-3 flex justify-between items-center text-xs font-medium text-muted-foreground border-b border-border">
      <div className="flex items-center space-x-1">
        <span className="material-icons-round text-sm">smart_toy</span>
        <span>{isActive && robot ? robot.name : '미연결'}</span>
      </div>
      <div className="flex items-center space-x-1">
        <span className="material-icons-round text-sm">timer</span>
        {isActive && isTaskMode ? (
          <span className="bg-primary/10 text-primary px-1.5 py-0.5 rounded text-[10px] font-bold">Task</span>
        ) : (
          <span>{isActive ? formatTime(session.remainingTime) : '—'}</span>
        )}
      </div>
      <div className={`flex items-center space-x-1 ${isActive && robot?.mode ? 'text-primary' : ''}`}>
        <span className="material-icons-round text-sm">{getModeIcon()}</span>
        <span>{getModeName()}</span>
      </div>
    </div>
  );
}

import { useAppStore } from '@/store/appStore';

export function ActiveSessionCard() {
  const { robot, session } = useAppStore();

  const formatRemainingTime = (seconds: number) => {
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    if (hours > 0) {
      return `${hours}h ${mins}m left`;
    }
    return `${mins}m left`;
  };

  const batteryPercentage = robot?.battery || 0;
  const progressWidth = `${Math.min(batteryPercentage, 100)}%`;

  return (
    <div className="bg-card-lavender dark:bg-purple-900/40 rounded-3xl p-6 relative overflow-hidden active-press">
      {/* Decoration */}
      <div className="card-decoration -right-6 -top-6 w-32 h-32 bg-white/30" />

      <div className="relative z-10">
        {/* Header */}
        <div className="flex justify-between items-start mb-4">
          <div>
            <p className="text-sm font-medium text-slate-600 dark:text-slate-300">Active Session</p>
            <h2 className="text-2xl font-bold text-slate-900 dark:text-white">Shopping Mall Trip</h2>
          </div>
          <button className="w-8 h-8 rounded-full bg-white/40 dark:bg-white/20 flex items-center justify-center">
            <span className="material-icons-round text-slate-700 dark:text-white text-lg">more_horiz</span>
          </button>
        </div>

        {/* Stats */}
        <div className="flex justify-between items-end mb-4">
          <div>
            <p className="text-3xl font-bold text-slate-900 dark:text-white">{batteryPercentage}%</p>
            <p className="text-xs text-slate-600 dark:text-slate-300">Battery Remaining</p>
          </div>
          <div className="flex items-center gap-2">
            <span className="bg-slate-900/10 dark:bg-white/20 backdrop-blur-sm rounded-full px-4 py-2 text-sm font-semibold text-slate-800 dark:text-white">
              {formatRemainingTime(session.remainingTime)}
            </span>
            <button className="w-10 h-10 rounded-full bg-slate-900 dark:bg-white flex items-center justify-center">
              <span className="material-icons-round text-white dark:text-slate-900">arrow_forward</span>
            </button>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="h-1.5 bg-white/40 dark:bg-white/20 rounded-full overflow-hidden">
          <div 
            className="h-full bg-slate-800 dark:bg-white rounded-full transition-all duration-300"
            style={{ width: progressWidth }}
          />
        </div>
      </div>
    </div>
  );
}

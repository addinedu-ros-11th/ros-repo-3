import { useRobotStore } from '@/stores/robotStore';


export function HomePage() {
  const { sessionState, robot, session, activeMode, sessionTime, setShowPinOverlay, lockboxSlots, addNotification } = useRobotStore();

  const formatTime = (seconds: number) => {
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    if (hrs > 0) {
      return `${hrs}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const fullSlots = lockboxSlots.filter(s => s.status === 'FULL').length;
  const reservedSlots = lockboxSlots.filter(s => s.status === 'RESERVED').length;

  const getModeIcon = () => {
    switch (activeMode) {
      case 'GUIDE': return 'alt_route';
      case 'FOLLOW': return 'directions_run';
      case 'PICKUP': return 'shopping_bag';
      default: return null;
    }
  };

  // INACTIVE State
  if (sessionState === 'INACTIVE') {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="robot-card-white max-w-lg w-full text-center py-16 px-8">
          <div className="absolute -right-10 -top-10 w-48 h-48 bg-slate-200/50 rounded-full blur-3xl" />
          <span className="material-icons-round text-6xl text-slate-300 dark:text-slate-600 mb-4 block">smart_toy</span>
          <h1 className="text-2xl font-bold text-slate-400 dark:text-slate-500 mb-2">No Active Session</h1>
          <p className="text-sm text-slate-400 dark:text-slate-500 mb-8">Waiting at station</p>
          
          <div className="space-y-3 text-sm text-muted-foreground">
            <div className="flex items-center justify-center space-x-2">
              <span className="material-icons-round text-base">smart_toy</span>
              <span>{robot.name}</span>
            </div>
            <div className="flex items-center justify-center space-x-2">
              <span className="material-icons-round text-base">battery_std</span>
              <span>{robot.battery}%</span>
            </div>
            <div className="flex items-center justify-center space-x-2">
              <span className="material-icons-round text-base">signal_wifi_4_bar</span>
              <span>{robot.networkStrength}</span>
            </div>
          </div>

          {/* Demo: Start Session Button */}
          <button
            onClick={() => setShowPinOverlay(true)}
            className="btn-primary mt-8"
          >
            <span className="material-icons-round mr-2 text-lg align-middle">play_arrow</span>
            Start Demo Session
          </button>
        </div>
      </div>
    );
  }

  // APPROACHING State
  if (sessionState === 'APPROACHING' || sessionState === 'PIN_MATCHING') {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="robot-card-lavender max-w-lg w-full text-center py-12 px-8">
          <div className="absolute -right-10 -top-10 w-48 h-48 bg-white/30 rounded-full blur-3xl" />
          <div className="relative z-10">
            <div className="inline-flex items-center space-x-2 bg-white/30 rounded-full px-4 py-2 mb-6">
              <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
              <span className="text-xs font-semibold text-slate-700">APPROACHING</span>
            </div>
            
            <h1 className="text-2xl font-bold text-slate-800 mb-6">Approaching Customer</h1>
            
            <div className="mb-6">
              <span className="text-5xl font-bold text-primary">ETA 00:45</span>
            </div>
            
            <div className="inline-flex items-center space-x-2 bg-white/50 rounded-xl px-4 py-2">
              <span className="material-icons-round text-sm text-slate-600">schedule</span>
              <span className="text-sm font-medium text-slate-700">TIME — 1h 30m</span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ACTIVE State - Dashboard
  return (
    <div className="grid grid-cols-3 gap-6">
      {/* Left Column - Session Summary */}
      <div className="col-span-2 space-y-6">
        {/* Session Summary Card */}
        <div className="robot-card-lavender">
          <div className="absolute -right-10 -top-10 w-48 h-48 bg-white/20 rounded-full blur-3xl" />
          <div className="relative z-10">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center space-x-3">
                <span className="badge-active">
                  <span className="w-2 h-2 rounded-full bg-emerald-500" />
                  Active Session
                </span>
                <span className="bg-white/40 px-3 py-1 rounded-full text-xs font-bold text-slate-700">
                  {session?.type === 'TIME' ? 'TIME' : 'TASK'}
                </span>
              </div>
              {activeMode && (
                <div className="flex items-center space-x-2 bg-white/40 rounded-xl px-4 py-2">
                  <span className="material-icons-round text-sm text-slate-700">{getModeIcon()}</span>
                  <span className="text-sm font-semibold text-slate-700">
                    {activeMode === 'GUIDE' ? 'Guide' : activeMode === 'FOLLOW' ? 'Follow Me' : 'Pickup'}
                  </span>
                </div>
              )}
            </div>

            <div className="mb-4">
              <p className="text-sm font-medium text-slate-600 mb-1">Remaining Time</p>
              <span className="text-5xl font-bold text-slate-800">{formatTime(session?.remainingTime || 0)}</span>
            </div>

            <div className="h-2 bg-white/40 rounded-full overflow-hidden">
              <div
                className="h-full bg-slate-800 rounded-full transition-all duration-1000"
                style={{ width: `${((5400 - (session?.remainingTime || 0)) / 5400) * 100}%` }}
              />
            </div>
          </div>
        </div>

        {/* Current Mission Card */}
        <div className="robot-card-white">
          <h3 className="text-lg font-bold text-foreground mb-3">Current Mission</h3>
          {activeMode ? (
            <div className="flex items-center space-x-3">
              <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
                <span className="material-icons-round text-primary">{getModeIcon()}</span>
              </div>
              <div>
                <p className="font-semibold text-foreground">
                  {activeMode === 'GUIDE' ? 'Heading to destination' : activeMode === 'FOLLOW' ? 'Following customer' : 'Pickup in progress'}
                </p>
                <p className="text-sm text-muted-foreground">
                  {activeMode === 'GUIDE' ? 'ETA 2 min' : activeMode === 'FOLLOW' ? 'Tracking active' : 'Awaiting pickup'}
                </p>
              </div>
            </div>
          ) : (
            <div className="flex items-center space-x-3 text-muted-foreground">
              <span className="material-icons-round text-2xl">hourglass_empty</span>
              <p>No active mission. Select a mode to begin.</p>
            </div>
          )}
        </div>

        {/* Recent Events */}
        <div className="robot-card-white">
          <h3 className="text-lg font-bold text-foreground mb-3">Recent Events</h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between text-sm">
              <div className="flex items-center space-x-3">
                <div className="w-8 h-8 rounded-full bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center">
                  <span className="material-icons-round text-emerald-600 text-sm">place</span>
                </div>
                <span className="text-foreground">Arrived at Zara</span>
              </div>
              <span className="text-muted-foreground">10:30 AM</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <div className="flex items-center space-x-3">
                <div className="w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
                  <span className="material-icons-round text-blue-600 text-sm">lock_open</span>
                </div>
                <span className="text-foreground">Lockbox Slot 2 opened</span>
              </div>
              <span className="text-muted-foreground">10:15 AM</span>
            </div>
          </div>
        </div>
      </div>

      {/* Right Column */}
      <div className="space-y-6">
        {/* Lockbox Summary */}
        <div className="robot-card-lime">
          <div className="absolute -right-8 -top-8 w-40 h-40 bg-emerald-200/30 rounded-full blur-3xl" />
          <div className="relative z-10">
            <h3 className="text-lg font-bold text-slate-800 mb-4">Lockbox Status</h3>
            
            <div className="flex justify-center space-x-2 mb-4">
              {lockboxSlots.map((slot) => (
                <div
                  key={slot.number}
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${
                    slot.status === 'FULL'
                      ? 'bg-blue-500 text-white'
                      : slot.status === 'RESERVED'
                      ? 'bg-pink-500 text-white'
                      : 'bg-slate-300 text-slate-600'
                  }`}
                >
                  {slot.number}
                </div>
              ))}
            </div>
            
            <p className="text-center text-sm font-medium text-slate-700">
              {fullSlots + reservedSlots}/5 occupied
            </p>
          </div>
        </div>

        {/* Customer Info */}
        <div className="robot-card-white">
          <h3 className="text-lg font-bold text-foreground mb-3">Customer</h3>
          <div className="flex items-center space-x-3">
            <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center">
              <span className="material-icons-round text-primary">person</span>
            </div>
            <div>
              <p className="font-semibold text-foreground">{session?.customerName || 'Customer'}</p>
              <p className="text-sm text-muted-foreground">Active session</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

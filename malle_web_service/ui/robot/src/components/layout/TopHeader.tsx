import { useRobotStore } from '@/stores/robotStore';
import { useEffect, useState } from 'react';

export function TopHeader() {
  const { robot, session, sessionState, activeMode, toggleNotificationPanel, notifications } = useRobotStore();
  const [currentTime, setCurrentTime] = useState(new Date());

  useEffect(() => {
    const interval = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(interval);
  }, []);

  const formatRemainingTime = (seconds: number) => {
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    if (hrs > 0) {
      return `${hrs}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const getModeIcon = () => {
    switch (activeMode) {
      case 'GUIDE': return 'alt_route';
      case 'FOLLOW': return 'directions_run';
      case 'PICKUP': return 'shopping_bag';
      default: return 'remove';
    }
  };

  const getModeName = () => {
    switch (activeMode) {
      case 'GUIDE': return 'Guide';
      case 'FOLLOW': return 'Follow Me';
      case 'PICKUP': return 'Pickup';
      default: return '—';
    }
  };

  const getStatusDot = () => {
    switch (sessionState) {
      case 'ACTIVE':
        return <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />;
      case 'APPROACHING':
      case 'PIN_MATCHING':
        return <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />;
      default:
        return <span className="w-2 h-2 rounded-full bg-slate-400" />;
    }
  };

  const getStatusLabel = () => {
    switch (sessionState) {
      case 'ACTIVE': return 'ACTIVE';
      case 'APPROACHING': return 'APPROACHING';
      case 'PIN_MATCHING': return 'MATCHING';
      default: return 'INACTIVE';
    }
  };

  const getStatusLabelClass = () => {
    switch (sessionState) {
      case 'ACTIVE': return 'text-emerald-600 dark:text-emerald-400';
      case 'APPROACHING':
      case 'PIN_MATCHING': return 'text-amber-600 dark:text-amber-400';
      default: return 'text-slate-500';
    }
  };

  const getBatteryIcon = () => {
    if (robot.battery > 80) return 'battery_full';
    if (robot.battery > 50) return 'battery_std';
    if (robot.battery > 20) return 'battery_3_bar';
    return 'battery_alert';
  };

  const getNetworkIcon = () => {
    switch (robot.networkStrength) {
      case 'Strong': return 'signal_wifi_4_bar';
      case 'Weak': return 'signal_wifi_2_bar';
      default: return 'signal_wifi_off';
    }
  };

  const unreadCount = notifications.filter(n => !n.read).length;

  return (
    <header className="h-14 px-6 flex items-center justify-between bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 shadow-sm z-30 fixed top-0 left-0 right-0">
      {/* Left: Robot info cluster */}
      <div className="flex items-center space-x-6 text-sm font-medium">
        <div className="flex items-center space-x-2">
          <span className="material-icons-round text-primary text-lg">smart_toy</span>
          <span className="font-bold text-slate-900 dark:text-white">{robot.name}</span>
        </div>
        <div className="flex items-center space-x-1.5">
          {getStatusDot()}
          <span className={`text-xs font-semibold ${getStatusLabelClass()}`}>{getStatusLabel()}</span>
        </div>
        <div className="flex items-center space-x-1 text-slate-500">
          <span className="material-icons-round text-sm">timer</span>
          <span>{sessionState === 'ACTIVE' && session ? formatRemainingTime(session.remainingTime) : '—'}</span>
        </div>
        {activeMode && (
          <div className="flex items-center space-x-1 text-primary">
            <span className="material-icons-round text-sm">{getModeIcon()}</span>
            <span className="font-semibold">{getModeName()}</span>
          </div>
        )}
        <div className="flex items-center space-x-1 text-slate-500">
          <span className="material-icons-round text-sm">speed</span>
          <span>{robot.status === 'IDLE' ? 'Idle' : robot.status === 'MOVING' ? 'Moving' : robot.status === 'WAITING' ? 'Waiting' : 'Stopped'}</span>
        </div>
      </div>

      {/* Right: Battery, Network, Alert */}
      <div className="flex items-center space-x-4">
        <div className="flex items-center space-x-1 text-xs text-slate-500">
          <span className="material-icons-round text-sm">{getBatteryIcon()}</span>
          <span>{robot.battery}%</span>
        </div>
        <div className="flex items-center space-x-1 text-xs text-slate-500">
          <span className="material-icons-round text-sm">{getNetworkIcon()}</span>
          <span>{robot.networkStrength}</span>
        </div>
        <button
          onClick={toggleNotificationPanel}
          className="p-2 rounded-full hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors relative"
        >
          <span className="material-icons-round text-slate-600 dark:text-slate-400 text-xl">notifications</span>
          {unreadCount > 0 && (
            <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full" />
          )}
        </button>
      </div>
    </header>
  );
}

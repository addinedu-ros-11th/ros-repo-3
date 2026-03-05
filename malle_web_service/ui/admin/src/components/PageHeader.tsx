import { useState, useEffect, useRef, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { MI } from './MaterialIcon';
import { useDashboard } from '@/context/DashboardContext';
import { useToast } from '@/hooks/use-toast';
import operatorAvatar from '@/assets/operator-avatar.png';

interface PageHeaderProps {
  title: string;
  subtitle: string;
}

export default function PageHeader({ title, subtitle }: PageHeaderProps) {
  const { darkMode, toggleDarkMode, robots, missions, events, selectRobot, setExpandedMissionId, setExpandedAlertId } = useDashboard();
  const { toast } = useToast();
  const navigate = useNavigate();
  const [profileOpen, setProfileOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);

  // Debounce
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQuery(query), 300);
    return () => clearTimeout(t);
  }, [query]);

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setSearchOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setSearchOpen(false);
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, []);

  const results = useMemo(() => {
    if (!debouncedQuery.trim()) return null;
    const q = debouncedQuery.toLowerCase();
    const matchedRobots = robots.filter(r => r.id.toLowerCase().includes(q));
    const matchedMissions = missions.filter(m =>
      m.currentTarget.toLowerCase().includes(q) ||
      m.type.toLowerCase().includes(q) ||
      m.robotId.toLowerCase().includes(q)
    );
    const matchedAlerts = events.filter(e =>
      e.message.toLowerCase().includes(q) ||
      e.type.toLowerCase().includes(q) ||
      e.robotId.toLowerCase().includes(q)
    );
    if (!matchedRobots.length && !matchedMissions.length && !matchedAlerts.length) return 'empty';
    return { robots: matchedRobots, missions: matchedMissions, alerts: matchedAlerts };
  }, [debouncedQuery, robots, missions, events]);

  const handleRobotClick = (robotId: string) => {
    selectRobot(robotId);
    navigate('/fleet-map');
    setQuery('');
    setSearchOpen(false);
  };

  const handleMissionClick = (missionId: string) => {
    setExpandedMissionId(missionId);
    navigate('/missions');
    setQuery('');
    setSearchOpen(false);
  };

  const handleAlertClick = (alertId: string) => {
    setExpandedAlertId(alertId);
    navigate('/events');
    setQuery('');
    setSearchOpen(false);
  };

  const statusColors: Record<string, string> = {
    MOVING: 'text-emerald-500',
    WAITING: 'text-amber-500',
    E_STOP: 'text-red-500',
    CHARGING: 'text-blue-500',
    OFFLINE: 'text-muted-foreground',
    HEADING_MAINTENANCE: 'text-purple-500',
    HEADING_STATION: 'text-blue-500',
  };

  return (
    <>
      <header className="flex justify-between items-center gap-4 mb-8">
        <div>
          <h2 className="text-3xl font-bold text-foreground">{title}</h2>
          <p className="text-muted-foreground">{subtitle}</p>
        </div>
        <div className="flex items-center gap-4">
          <div className="relative w-80" ref={searchRef}>
            <MI icon="search" className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground text-xl" />
            <input
              className="w-full pl-10 pr-4 py-2.5 rounded-xl border-none bg-card shadow-sm focus:ring-2 focus:ring-primary text-foreground placeholder:text-muted-foreground text-sm"
              placeholder="Search robots, missions, or alerts..."
              value={query}
              onChange={e => { setQuery(e.target.value); setSearchOpen(true); }}
              onFocus={() => query && setSearchOpen(true)}
            />

            {/* Search Results Dropdown */}
            {searchOpen && results && (
              <div className="absolute top-full left-0 right-0 mt-1 bg-card rounded-xl shadow-xl border border-border max-h-80 overflow-y-auto z-50">
                {results === 'empty' ? (
                  <div className="p-4 text-sm text-muted-foreground text-center">No results found</div>
                ) : (
                  <>
                    {results.robots.length > 0 && (
                      <div>
                        <p className="px-3 pt-3 pb-1 text-xs font-bold text-muted-foreground uppercase tracking-wider">🤖 Robots</p>
                        {results.robots.map(r => (
                          <button key={r.id} onClick={() => handleRobotClick(r.id)} className="w-full text-left px-3 py-2 hover:bg-secondary/50 rounded-lg flex items-center gap-3 transition-colors">
                            <MI icon="smart_toy" className="text-muted-foreground text-lg" />
                            <div>
                              <span className="text-sm font-bold text-foreground">{r.id}</span>
                              <span className={`ml-2 text-xs font-semibold ${statusColors[r.status] || 'text-muted-foreground'}`}>{r.status}</span>
                            </div>
                          </button>
                        ))}
                      </div>
                    )}
                    {results.missions.length > 0 && (
                      <div>
                        <p className="px-3 pt-3 pb-1 text-xs font-bold text-muted-foreground uppercase tracking-wider">📋 Missions</p>
                        {results.missions.map(m => (
                          <button key={m.id} onClick={() => handleMissionClick(m.id)} className="w-full text-left px-3 py-2 hover:bg-secondary/50 rounded-lg flex items-center gap-3 transition-colors">
                            <MI icon="flag" className="text-muted-foreground text-lg" />
                            <div>
                              <span className="text-sm font-bold text-foreground">{m.currentTarget}</span>
                              <span className="ml-2 text-xs text-muted-foreground">{m.robotId} · {m.status}</span>
                            </div>
                          </button>
                        ))}
                      </div>
                    )}
                    {results.alerts.length > 0 && (
                      <div>
                        <p className="px-3 pt-3 pb-1 text-xs font-bold text-muted-foreground uppercase tracking-wider">🔔 Alerts</p>
                        {results.alerts.map(a => (
                          <button key={a.id} onClick={() => handleAlertClick(a.id)} className="w-full text-left px-3 py-2 hover:bg-secondary/50 rounded-lg flex items-center gap-3 transition-colors">
                            <MI icon="notifications" className="text-muted-foreground text-lg" />
                            <div className="min-w-0">
                              <span className="text-sm text-foreground truncate block">{a.message}</span>
                              <span className="text-xs text-muted-foreground">{a.robotId} · {a.timestamp}</span>
                            </div>
                          </button>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </div>
            )}
          </div>
          <button
            onClick={() => setProfileOpen(true)}
            className="w-12 h-12 rounded-full overflow-hidden shadow-md hover:scale-105 active:scale-95 transition-transform cursor-pointer border-2 border-border"
          >
            <img src={operatorAvatar} alt="Operator" className="w-full h-full object-cover" />
          </button>
        </div>
      </header>

      {/* Dark mode toggle */}
      <button
        onClick={toggleDarkMode}
        className="fixed bottom-6 right-6 w-12 h-12 bg-card rounded-full shadow-lg border border-border flex items-center justify-center hover:scale-110 active:scale-95 z-[60] transition-transform"
      >
        <MI icon={darkMode ? 'light_mode' : 'dark_mode'} className="text-muted-foreground text-xl" />
      </button>

      {/* Operator Profile Panel */}
      {profileOpen && (
        <div className="fixed inset-0 z-50" onClick={() => setProfileOpen(false)}>
          <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" />
          <div
            className="absolute top-0 right-0 h-full w-96 bg-card border-l border-border shadow-2xl z-50 animate-in slide-in-from-right duration-300 flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              onClick={() => setProfileOpen(false)}
              className="absolute top-4 right-4 p-1.5 rounded-lg hover:bg-secondary transition-colors"
            >
              <MI icon="close" className="text-muted-foreground text-xl" />
            </button>

            <div className="flex flex-col items-center pt-10 pb-6 px-6">
              <img
                src={operatorAvatar}
                alt="Operator avatar"
                className="w-60 h-60 rounded-full border-4 border-border shadow-md mb-4 object-cover"
              />
              <h3 className="text-xl font-bold text-foreground">Operator-133</h3>
              <span className="mt-2 bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400 text-xs font-bold px-3 py-1 rounded-full">
                Full Access
              </span>
            </div>

            <div className="flex-1 overflow-y-auto px-6 space-y-2">
              {[
                { icon: '🆔', label: 'Operator ID', value: 'Operator-133' },
                { icon: '🔐', label: 'Access Level', value: 'All Authorities (Full Admin)' },
                { icon: '🕐', label: 'Session Started', value: `${new Date().toLocaleDateString()} — 08:30 AM` },
                { icon: '📡', label: 'Connection', value: 'Online — Secure' },
                { icon: '🏢', label: 'Assigned Facility', value: 'MALL·E Central Hub' },
                { icon: '📅', label: 'Last Login', value: 'Yesterday, 09:15 AM' },
              ].map((item) => (
                <div key={item.label} className="flex items-center gap-3 bg-secondary/50 rounded-xl p-3">
                  <span className="text-lg">{item.icon}</span>
                  <div className="min-w-0">
                    <p className="text-xs text-muted-foreground">{item.label}</p>
                    <p className="text-sm font-semibold text-foreground truncate">{item.value}</p>
                  </div>
                </div>
              ))}
            </div>

            <div className="p-6">
              <button
                onClick={() => {
                  toast({ title: 'Demo Mode', description: 'Sign out is disabled in demo mode.' });
                }}
                className="w-full py-3 bg-secondary text-foreground rounded-xl font-bold flex items-center justify-center gap-2 hover:bg-secondary/80 active:scale-95 transition-all"
              >
                <MI icon="logout" className="text-xl" />
                Sign Out
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

import { Link, useLocation } from 'react-router-dom';
import { MI } from './MaterialIcon';
import { useDashboard } from '@/context/DashboardContext';

const navItems = [
  { label: 'Overview', icon: 'grid_view', path: '/' },
  { label: 'Fleet Map', icon: 'map', path: '/fleet-map' },
  { label: 'Manual Control', icon: 'settings_remote', path: '/manual-control' },
  { label: 'Zones', icon: 'layers', path: '/zones' },
  { label: 'Missions', icon: 'assignment', path: '/missions' },
  { label: 'Analytics', icon: 'bar_chart', path: '/analytics' },
  { label: 'Events', icon: 'notifications_active', path: '/events' },
];

export default function AppSidebar() {
  const location = useLocation();
  const { emergencyBanner } = useDashboard();

  return (
    <aside className="w-64 shrink-0 border-r border-border p-6 flex flex-col gap-8 sticky top-0 h-screen bg-card overflow-y-auto">
      {/* Logo */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 bg-primary rounded-xl flex items-center justify-center">
          <MI icon="smart_toy" className="text-primary-foreground text-xl" />
        </div>
        <span className="font-extrabold text-xl tracking-tight italic text-foreground">
          MALL·E <span className="text-primary ml-2">FMS</span>
        </span>
      </div>

      {/* Navigation */}
      <nav className="flex flex-col gap-1">
        {navItems.map(item => {
          const isActive = location.pathname === item.path;
          return (
            <Link
              key={item.path}
              to={item.path}
              className={`flex items-center gap-3 p-3 rounded-xl text-sm font-medium transition-all ${
                isActive
                  ? 'bg-secondary text-primary font-semibold'
                  : 'text-muted-foreground hover:bg-secondary/60'
              }`}
            >
              <MI icon={item.icon} className="text-xl" />
              <span>{item.label}</span>
              {item.label === 'Events' && emergencyBanner?.active && (
                <span className="ml-auto w-2 h-2 bg-critical-red rounded-full animate-ping" />
              )}
            </Link>
          );
        })}
      </nav>

      {/* System Status */}
      <div className="mt-auto p-4 bg-primary/10 rounded-2xl">
        <p className="text-xs text-primary font-bold mb-1 uppercase tracking-wider">System Status</p>
        <div className="flex items-center gap-2">
          <div className="relative">
            <div className="w-2 h-2 bg-emerald-500 rounded-full" />
            <div className="w-2 h-2 bg-emerald-500 rounded-full absolute inset-0 animate-ping" />
          </div>
          <span className="text-sm font-medium text-foreground">Core API: Online</span>
        </div>
        <div className="flex items-center gap-2 mt-1">
          <div className="w-2 h-2 bg-emerald-500 rounded-full" />
          <span className="text-xs text-muted-foreground">MQTT Broker: Connected</span>
        </div>
      </div>
    </aside>
  );
}

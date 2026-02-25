import { Link } from 'react-router-dom';
import { useDashboard } from '@/context/DashboardContext';
import { MI } from '@/components/MaterialIcon';
import PageHeader from '@/components/PageHeader';

const kpiCards = [
  { label: 'Online Robots', value: '18/24', badge: '+12%', badgeColor: '', bg: 'bg-bright-blue text-primary-foreground', icon: 'smart_toy', ghost: 'precision_manufacturing' },
  { label: 'Active Missions', value: '14', badge: 'LIVE', badgeColor: '', bg: 'bg-lavender text-foreground', icon: 'task_alt', ghost: 'route' },
  { label: 'E-stop Events', value: '03', badge: '-30%', badgeColor: 'text-critical-red', bg: 'bg-lime-vibrant text-foreground', icon: 'pan_tool', ghost: 'warning' },
  { label: 'Manual Takes', value: '07', badge: 'REQD', badgeColor: '', bg: 'bg-vibrant-orange text-primary-foreground', icon: 'videocam', ghost: 'sports_esports' },
];

const statusDot: Record<string, string> = {
  MOVING: 'bg-emerald-500',
  WAITING: 'bg-muted-foreground',
  E_STOP: 'bg-critical-red',
  CHARGING: 'bg-bright-blue',
  OFFLINE: 'bg-muted-foreground',
  HEADING_MAINTENANCE: 'bg-amber-500',
  HEADING_STATION: 'bg-amber-500',
};

const statusLabel: Record<string, string> = {
  MOVING: 'Moving',
  WAITING: 'Waiting',
  E_STOP: 'E-Stop',
  CHARGING: 'Charging',
  OFFLINE: 'Offline',
  HEADING_MAINTENANCE: 'Heading to Maintenance',
  HEADING_STATION: 'Heading to Station',
};

const modeBadge: Record<string, string> = {
  GUIDE: 'bg-secondary text-muted-foreground',
  FOLLOW: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  PICKUP: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
};

export default function OverviewPage() {
  const { robots, events } = useDashboard();
  const activeRobots = robots.filter(r => r.status !== 'OFFLINE');
  const activeZones = 3;

  return (
    <div>
      <PageHeader title="Dashboard Overview" subtitle={`Monitoring ${activeRobots.length} active units across ${activeZones} zones.`} />

      {/* KPI Cards */}
      <div className="grid grid-cols-4 gap-6 mb-8">
        {kpiCards.map(card => (
          <div key={card.label} className={`relative overflow-hidden group rounded-3xl p-6 shadow-sm ${card.bg}`}>
            <div className="flex items-center justify-between mb-4">
              <div className="bg-white/20 p-2 rounded-xl">
                <MI icon={card.icon} className="text-2xl" />
              </div>
              <span className={`text-xs font-bold bg-white/20 px-2 py-1 rounded-full ${card.badgeColor}`}>{card.badge}</span>
            </div>
            <p className="text-sm font-medium opacity-80">{card.label}</p>
            <p className="text-4xl font-bold mt-1">{card.value}</p>
            <span className="kpi-ghost-icon material-icons-round">{card.ghost}</span>
          </div>
        ))}
      </div>

      {/* Main content */}
      <div className="grid grid-cols-3 gap-8">
        {/* Fleet Status Table */}
        <div className="lg:col-span-2 bg-card rounded-3xl p-6 shadow-sm border border-border">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-bold text-foreground">Active Fleet Status</h3>
            <Link to="/fleet-map" className="text-primary text-sm font-semibold hover:underline flex items-center gap-1">
              View All Map <MI icon="arrow_forward" className="text-sm" />
            </Link>
          </div>
          <table className="w-full">
            <thead>
              <tr className="text-left text-muted-foreground text-xs uppercase tracking-wider">
                <th className="pb-4 font-semibold">Robot ID</th>
                <th className="pb-4 font-semibold">Battery</th>
                <th className="pb-4 font-semibold">Mode</th>
                <th className="pb-4 font-semibold">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {robots.map(robot => (
                <tr key={robot.id} className="group hover:bg-secondary/50 transition-colors">
                  <td className="py-4">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-secondary flex items-center justify-center">
                        <MI icon="smart_toy" className="text-muted-foreground text-sm" />
                      </div>
                      <span className="font-bold text-foreground text-sm">{robot.id}</span>
                    </div>
                  </td>
                  <td className="py-4">
                    <div className="flex items-center gap-2">
                      <div className="w-20 h-2 rounded-full bg-secondary overflow-hidden">
                        <div
                          className={`h-full rounded-full ${robot.battery > 50 ? 'bg-emerald-500' : robot.battery > 20 ? 'bg-amber-500' : 'bg-critical-red'}`}
                          style={{ width: `${robot.battery}%` }}
                        />
                      </div>
                      <span className="text-xs text-muted-foreground">{robot.battery}%</span>
                    </div>
                  </td>
                  <td className="py-4">
                    {robot.mode ? (
                      <span className={`text-xs font-bold px-3 py-1 rounded-full ${modeBadge[robot.mode]}`}>{robot.mode}</span>
                    ) : (
                      <span className="text-xs text-muted-foreground">—</span>
                    )}
                  </td>
                  <td className="py-4">
                    <div className="flex items-center gap-2">
                      <div className={`w-2 h-2 rounded-full ${statusDot[robot.status]}`} />
                      <span className="text-sm text-foreground">{statusLabel[robot.status] || robot.status}</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Right sidebar */}
        <div className="space-y-6">
          {/* Health Summary */}
          <div className="bg-card rounded-3xl p-6 shadow-sm border border-border">
            <h3 className="text-lg font-bold text-foreground mb-4">Health Summary</h3>
            <div className="space-y-3">
              <div className="p-3 bg-red-50 dark:bg-red-900/10 rounded-2xl border border-red-100 dark:border-red-900/30 flex items-center gap-3 cursor-pointer hover:bg-red-100 dark:hover:bg-red-900/20 transition-colors">
                <MI icon="battery_alert" className="text-critical-red text-xl" />
                <div className="flex-1">
                  <p className="text-sm font-bold text-foreground">Low Battery</p>
                  <p className="text-xs text-muted-foreground">3 units critical</p>
                </div>
                <MI icon="chevron_right" className="text-muted-foreground" />
              </div>
              <div className="p-3 bg-amber-50 dark:bg-amber-900/10 rounded-2xl border border-amber-100 dark:border-amber-900/30 flex items-center gap-3 cursor-pointer hover:bg-amber-100 dark:hover:bg-amber-900/20 transition-colors">
                <MI icon="wifi_off" className="text-amber-500 text-xl" />
                <div className="flex-1">
                  <p className="text-sm font-bold text-foreground">Comms Loss</p>
                  <p className="text-xs text-muted-foreground">1 unit flickering</p>
                </div>
                <MI icon="chevron_right" className="text-muted-foreground" />
              </div>
              <div className="p-3 bg-blue-50 dark:bg-blue-900/10 rounded-2xl border border-blue-100 dark:border-blue-900/30 flex items-center gap-3 cursor-pointer hover:bg-blue-100 dark:hover:bg-blue-900/20 transition-colors">
                <MI icon="settings" className="text-bright-blue text-xl" />
                <div className="flex-1">
                  <p className="text-sm font-bold text-foreground">Sensor Sync</p>
                  <p className="text-xs text-muted-foreground">Routine calibration</p>
                </div>
                <MI icon="chevron_right" className="text-muted-foreground" />
              </div>
            </div>
          </div>

          {/* Recent Events */}
          <div className="bg-card rounded-3xl p-6 shadow-sm border border-border">
            <h3 className="text-lg font-bold text-foreground mb-4">Recent Events</h3>
            <div className="relative pl-6 space-y-4">
              <div className="absolute left-2 top-2 bottom-2 w-[2px] bg-border" />
              {events.slice(0, 4).map(event => {
                const dotColor = event.severity === 'CRITICAL' ? 'bg-critical-red' : event.severity === 'WARN' ? 'bg-amber-500' : 'bg-bright-blue';
                return (
                  <div key={event.id} className="relative">
                    <div className={`absolute -left-4 top-1 w-3 h-3 rounded-full border-2 border-card ${dotColor}`} />
                    <p className="text-xs text-muted-foreground">{event.timestamp}</p>
                    <p className="text-sm font-bold text-foreground">{event.message.split('—')[0].trim()}</p>
                    <p className="text-xs text-muted-foreground">{event.message.split('—')[1]?.trim()}</p>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Bottom Stats */}
      <div className="grid grid-cols-3 gap-6 mt-8">
        {[
          { icon: 'analytics', label: 'Uptime', value: '99.98%', bg: 'bg-lavender' },
          { icon: 'local_shipping', label: 'Missions Today', value: '1,240', bg: 'bg-lime-vibrant' },
          { icon: 'speed', label: 'Avg Speed', value: '1.2 m/s', bg: 'bg-vibrant-orange' },
        ].map(stat => (
          <div key={stat.label} className="bg-card rounded-3xl p-6 flex items-center gap-4 shadow-sm border border-border">
            <div className={`w-12 h-12 rounded-2xl ${stat.bg} flex items-center justify-center`}>
              <MI icon={stat.icon} className="text-foreground text-2xl" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">{stat.label}</p>
              <p className="text-2xl font-bold text-foreground">{stat.value}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

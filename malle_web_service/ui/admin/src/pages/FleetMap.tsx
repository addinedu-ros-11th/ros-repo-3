import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDashboard } from '@/context/DashboardContext';
import { MI } from '@/components/MaterialIcon';
import PageHeader from '@/components/PageHeader';

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

interface PendingAction {
  type: 'estop' | 'maintenance' | 'station';
  robotId: string;
}

const confirmConfig: Record<PendingAction['type'], { icon: string; confirmClass: string; label: string }> = {
  estop: { icon: 'warning', confirmClass: 'bg-critical-red hover:bg-red-600 text-primary-foreground', label: 'Trigger E-Stop' },
  maintenance: { icon: 'build', confirmClass: 'bg-primary hover:bg-primary/90 text-primary-foreground', label: 'Send to Maintenance' },
  station: { icon: 'home', confirmClass: 'bg-foreground/80 hover:bg-foreground/70 text-background', label: 'Return to Station' },
};

function getConfirmMessage(action: PendingAction): string {
  switch (action.type) {
    case 'estop':
      return `Are you sure you want to trigger E-Stop on ${action.robotId}? The robot will immediately halt all movement.`;
    case 'maintenance':
      return `Send ${action.robotId} to the Maintenance Center? The robot will navigate autonomously to maintenance.`;
    case 'station':
      return `Send ${action.robotId} back to Home Station? The robot will navigate autonomously to its station.`;
  }
}

export default function FleetMapPage() {
  const { robots, zones, selectedRobotId, selectRobot, triggerEStop, releaseEStop, startTeleop, sendToMaintenance, returnToStation } = useDashboard();
  const navigate = useNavigate();
  const [layers, setLayers] = useState({ robots: true, routes: true, zones: true, destinations: true });
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null);
  const selectedRobot = robots.find(r => r.id === selectedRobotId);

  const toggleLayer = (key: keyof typeof layers) => setLayers(prev => ({ ...prev, [key]: !prev[key] }));

  const executeAction = () => {
    if (!pendingAction) return;
    switch (pendingAction.type) {
      case 'estop': triggerEStop(pendingAction.robotId); break;
      case 'maintenance': sendToMaintenance(pendingAction.robotId); break;
      case 'station': returnToStation(pendingAction.robotId); break;
    }
    setPendingAction(null);
  };

  return (
    <div className="h-[calc(100vh-4rem)]">
      <PageHeader title="Fleet Map" subtitle="Real-time fleet monitoring" />

      <div className="flex gap-0 h-[calc(100%-6rem)] -mx-8 -mb-8">
        {/* Map Area */}
        <div className="flex-1 relative bg-secondary/30 overflow-hidden">
          {/* Layer toggles */}
          <div className="absolute top-4 left-4 z-10 flex gap-2">
            {Object.entries(layers).map(([key, active]) => (
              <button
                key={key}
                onClick={() => toggleLayer(key as keyof typeof layers)}
                className={`px-3 py-1.5 rounded-full text-xs font-bold shadow-sm border transition-all ${
                  active ? 'bg-primary text-primary-foreground border-primary' : 'bg-card text-muted-foreground border-border'
                }`}
              >
                {key.charAt(0).toUpperCase() + key.slice(1)}
              </button>
            ))}
          </div>

          {/* Grid pattern */}
          <svg className="w-full h-full" viewBox="0 0 450 380" preserveAspectRatio="xMidYMid meet">
            <defs>
              <pattern id="dotGrid" x="0" y="0" width="20" height="20" patternUnits="userSpaceOnUse">
                <circle cx="1" cy="1" r="1" className="fill-muted-foreground/20" />
              </pattern>
            </defs>
            <rect width="450" height="380" fill="url(#dotGrid)" />

            <image href="/map_end_end.png" x="0" y="0" width="450" height="380" preserveAspectRatio="xMidYMid meet" opacity="0.85" />

            {/* Zones */}
            {layers.zones && zones.map(zone => {
              const pts = zone.polygon.map(p => `${p.x},${p.y}`).join(' ');
              const fill = zone.type === 'RESTRICTED' ? 'rgba(239,68,68,0.15)' : zone.type === 'MAINTENANCE' ? 'rgba(168,85,247,0.15)' : zone.type === 'CONGESTED' ? 'rgba(234,179,8,0.15)' : 'rgba(249,115,22,0.15)';
              const stroke = zone.type === 'RESTRICTED' ? '#ef4444' : zone.type === 'MAINTENANCE' ? '#a855f7' : zone.type === 'CONGESTED' ? '#eab308' : '#f97316';
              return (
                <g key={zone.id}>
                  <polygon
                    points={pts}
                    fill={zone.active ? fill : 'none'}
                    stroke={stroke}
                    strokeWidth="2"
                    strokeDasharray={zone.active ? '' : '6 4'}
                    opacity={zone.active ? 1 : 0.4}
                  />
                  <text x={zone.polygon[0].x + 5} y={zone.polygon[0].y - 5} className="fill-muted-foreground text-[8px] font-bold">{zone.name}</text>
                </g>
              );
            })}

            {/* Routes */}
            {layers.routes && robots.filter(r => r.currentTarget).map(robot => (
              <line
                key={`route-${robot.id}`}
                x1={robot.position.x}
                y1={robot.position.y}
                x2={robot.position.x + 50}
                y2={robot.position.y - 30}
                stroke="hsl(239,84%,67%)"
                strokeWidth="1.5"
                strokeDasharray="4 4"
                opacity="0.5"
              />
            ))}

            {/* Robot markers */}
            {layers.robots && robots.map(robot => {
              const isSelected = robot.id === selectedRobotId;
              const fill = robot.status === 'E_STOP' ? '#ef4444'
                : robot.status === 'HEADING_MAINTENANCE' || robot.status === 'HEADING_STATION' ? '#f59e0b'
                : robot.status === 'MOVING' ? '#3b82f6'
                : robot.status === 'CHARGING' ? '#6366f1'
                : '#94a3b8';
              return (
                <g
                  key={robot.id}
                  className="cursor-pointer"
                  onClick={() => selectRobot(robot.id === selectedRobotId ? null : robot.id)}
                >
                  {isSelected && <circle cx={robot.position.x} cy={robot.position.y} r="18" fill="none" stroke={fill} strokeWidth="2" opacity="0.4">
                    <animate attributeName="r" from="14" to="22" dur="1.5s" repeatCount="indefinite" />
                    <animate attributeName="opacity" from="0.4" to="0" dur="1.5s" repeatCount="indefinite" />
                  </circle>}
                  {robot.status === 'E_STOP' && <circle cx={robot.position.x} cy={robot.position.y} r="14" fill={fill} opacity="0.2">
                    <animate attributeName="opacity" from="0.3" to="0" dur="1s" repeatCount="indefinite" />
                  </circle>}
                  <circle cx={robot.position.x} cy={robot.position.y} r="8" fill={fill} stroke="white" strokeWidth="2" />
                  <text x={robot.position.x} y={robot.position.y - 14} textAnchor="middle" className="fill-foreground text-[8px] font-bold">{robot.id}</text>
                </g>
              );
            })}

            {/* Destinations */}
            {layers.destinations && (
              <>
                {[{ name: 'Zara Store', x: 170, y: 50 }, { name: 'Nike', x: 80, y: 190 }, { name: 'Apple Store', x: 340, y: 100 }, { name: 'Starbucks', x: 200, y: 260 }].map(poi => (
                  <g key={poi.name}>
                    <rect x={poi.x - 3} y={poi.y - 3} width="6" height="6" rx="1" className="fill-primary" />
                    <text x={poi.x + 8} y={poi.y + 3} className="fill-muted-foreground text-[7px]">{poi.name}</text>
                  </g>
                ))}
              </>
            )}
          </svg>

          {/* Robot cards bottom scroll */}
          <div className="absolute bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-background/80 to-transparent">
            <div className="flex gap-4 overflow-x-auto pb-2">
              {robots.map(robot => (
                <div
                  key={robot.id}
                  onClick={() => selectRobot(robot.id)}
                  className={`bg-card rounded-2xl p-4 shadow-sm border shrink-0 w-56 cursor-pointer transition-all hover:shadow-md ${
                    robot.id === selectedRobotId ? 'border-primary ring-2 ring-primary/20' : 'border-border'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <MI icon="smart_toy" className="text-muted-foreground text-lg" />
                      <span className="font-bold text-sm text-foreground">{robot.id}</span>
                    </div>
                    <div className={`w-2 h-2 rounded-full ${statusDot[robot.status]}`} />
                  </div>
                  <div className="flex items-center gap-2 mb-1">
                    {robot.mode && <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${modeBadge[robot.mode]}`}>{robot.mode}</span>}
                    <span className="text-xs text-muted-foreground">{robot.battery}%</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    {statusLabel[robot.status] || robot.status}
                    {robot.currentTarget && ` → ${robot.currentTarget}`}
                    {robot.eta ? ` (${robot.eta}s)` : ''}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Detail Panel */}
        {selectedRobot && (
          <div className="w-96 border-l border-border bg-card p-6 overflow-y-auto">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h3 className="text-2xl font-bold text-foreground">{selectedRobot.id}</h3>
                <div className="flex items-center gap-2 mt-1">
                  {selectedRobot.mode && <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${modeBadge[selectedRobot.mode]}`}>{selectedRobot.mode}</span>}
                  <div className="flex items-center gap-1">
                    <div className={`w-2 h-2 rounded-full ${statusDot[selectedRobot.status]}`} />
                    <span className="text-sm text-muted-foreground">{statusLabel[selectedRobot.status] || selectedRobot.status}</span>
                  </div>
                </div>
              </div>
              <button onClick={() => selectRobot(null)} className="p-2 rounded-xl hover:bg-secondary transition-colors">
                <MI icon="close" className="text-muted-foreground" />
              </button>
            </div>

            {/* Session info */}
            <div className="bg-secondary/50 rounded-2xl p-4 mb-4">
              <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Current Mission</p>
              {selectedRobot.currentTarget ? (
                <>
                  <p className="text-2xl font-bold text-foreground">{selectedRobot.currentTarget}</p>
                  {selectedRobot.eta !== null && selectedRobot.eta > 0 && (
                    <p className="text-sm text-muted-foreground">ETA: {selectedRobot.eta}s</p>
                  )}
                </>
              ) : (
                <p className="text-sm text-muted-foreground">No active mission</p>
              )}
            </div>

            {/* Stats */}
            <div className="grid grid-cols-2 gap-3 mb-4">
              <div className="bg-secondary/50 rounded-xl p-3">
                <p className="text-xs text-muted-foreground">Battery</p>
                <p className="text-lg font-bold text-foreground">{selectedRobot.battery}%</p>
              </div>
              <div className="bg-secondary/50 rounded-xl p-3">
                <p className="text-xs text-muted-foreground">Comms</p>
                <p className="text-lg font-bold text-foreground">{selectedRobot.commsStatus}</p>
              </div>
              <div className="bg-secondary/50 rounded-xl p-3">
                <p className="text-xs text-muted-foreground">Sensors</p>
                <p className="text-lg font-bold text-foreground">{selectedRobot.sensorStatus}</p>
              </div>
              <div className="bg-secondary/50 rounded-xl p-3">
                <p className="text-xs text-muted-foreground">Last Seen</p>
                <p className="text-lg font-bold text-foreground">{selectedRobot.lastSeen}</p>
              </div>
            </div>

            {/* Warnings */}
            {(selectedRobot.battery < 20 || selectedRobot.commsStatus !== 'STRONG' || selectedRobot.eStopActive) && (
              <div className="space-y-2 mb-4">
                {selectedRobot.battery < 20 && (
                  <div className="p-3 bg-red-50 dark:bg-red-900/10 rounded-xl border border-red-100 dark:border-red-900/30 flex items-center gap-2">
                    <MI icon="battery_alert" className="text-critical-red" />
                    <span className="text-sm font-bold text-foreground">Battery Critical</span>
                  </div>
                )}
                {selectedRobot.commsStatus === 'WEAK' && (
                  <div className="p-3 bg-amber-50 dark:bg-amber-900/10 rounded-xl border border-amber-100 dark:border-amber-900/30 flex items-center gap-2">
                    <MI icon="wifi_off" className="text-amber-500" />
                    <span className="text-sm font-bold text-foreground">Weak Signal</span>
                  </div>
                )}
              </div>
            )}

            {/* E-Stop status */}
            <div className={`p-3 rounded-xl mb-4 flex items-center gap-2 ${selectedRobot.eStopActive ? 'bg-red-50 dark:bg-red-900/10 border border-red-200 dark:border-red-900/30' : 'bg-emerald-50 dark:bg-emerald-900/10 border border-emerald-200 dark:border-emerald-900/30'}`}>
              <MI icon={selectedRobot.eStopActive ? 'pan_tool' : 'check_circle'} className={selectedRobot.eStopActive ? 'text-critical-red' : 'text-emerald-500'} />
              <span className="text-sm font-bold text-foreground">E-Stop: {selectedRobot.eStopActive ? `ON (${selectedRobot.eStopSource})` : 'OFF'}</span>
            </div>

            {/* Action Buttons */}
            <div className="space-y-3">
              {selectedRobot.eStopActive ? (
                <button
                  onClick={() => releaseEStop(selectedRobot.id)}
                  className="w-full py-3 bg-emerald-500 text-primary-foreground rounded-xl font-bold shadow-lg flex items-center justify-center gap-2 hover:bg-emerald-600 active:scale-95 transition-all"
                >
                  <MI icon="play_circle" /> Resume — Clear E-Stop
                </button>
              ) : (
                <button
                  onClick={() => setPendingAction({ type: 'estop', robotId: selectedRobot.id })}
                  className="w-full py-3 bg-critical-red text-primary-foreground rounded-xl font-bold shadow-lg flex items-center justify-center gap-2 hover:bg-red-600 active:scale-95 transition-all"
                >
                  <MI icon="pan_tool" /> Trigger E-Stop
                </button>
              )}
              <button
                onClick={() => {
                  startTeleop(selectedRobot.id);
                  navigate('/manual-control');
                }}
                className="w-full py-3 bg-primary text-primary-foreground rounded-xl font-bold flex items-center justify-center gap-2 hover:bg-primary/90 active:scale-95 transition-all"
              >
                <MI icon="settings_remote" /> Take Manual Control
              </button>
              <button className="w-full py-3 bg-amber-500 text-primary-foreground rounded-xl font-bold flex items-center justify-center gap-2 hover:bg-amber-600 active:scale-95 transition-all">
                <MI icon="stop_circle" /> Stop Current Mission
              </button>
              <button
                onClick={() => setPendingAction({ type: 'maintenance', robotId: selectedRobot.id })}
                className="w-full py-3 bg-bright-blue text-primary-foreground rounded-xl font-bold flex items-center justify-center gap-2 hover:bg-blue-600 active:scale-95 transition-all"
              >
                <MI icon="build" /> Send to Maintenance
              </button>
              <button
                onClick={() => setPendingAction({ type: 'station', robotId: selectedRobot.id })}
                className="w-full py-3 bg-foreground/80 text-background rounded-xl font-bold flex items-center justify-center gap-2 hover:bg-foreground/70 active:scale-95 transition-all"
              >
                <MI icon="home" /> Return to Station
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Confirmation Dialog */}
      {pendingAction && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center" onClick={() => setPendingAction(null)}>
          <div className="bg-card rounded-2xl p-6 shadow-xl border border-border max-w-md w-full mx-4" onClick={e => e.stopPropagation()}>
            <div className="flex justify-center mb-4">
              <div className={`w-14 h-14 rounded-2xl flex items-center justify-center ${
                pendingAction.type === 'estop' ? 'bg-red-100 dark:bg-red-900/20' : pendingAction.type === 'maintenance' ? 'bg-blue-100 dark:bg-blue-900/20' : 'bg-secondary'
              }`}>
                <MI icon={confirmConfig[pendingAction.type].icon} className={`text-3xl ${
                  pendingAction.type === 'estop' ? 'text-critical-red' : pendingAction.type === 'maintenance' ? 'text-bright-blue' : 'text-foreground'
                }`} />
              </div>
            </div>
            <h3 className="text-lg font-bold text-foreground text-center mb-2">{confirmConfig[pendingAction.type].label}</h3>
            <p className="text-sm text-muted-foreground text-center mb-6">{getConfirmMessage(pendingAction)}</p>
            <div className="flex gap-3">
              <button
                onClick={() => setPendingAction(null)}
                className="flex-1 py-2.5 bg-secondary text-foreground rounded-xl font-bold hover:bg-secondary/80 transition-all"
              >
                Cancel
              </button>
              <button
                onClick={executeAction}
                className={`flex-1 py-2.5 rounded-xl font-bold active:scale-95 transition-all ${confirmConfig[pendingAction.type].confirmClass}`}
              >
                Confirm
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

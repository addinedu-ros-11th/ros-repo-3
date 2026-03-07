import { useState, useRef, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDashboard } from '@/context/DashboardContext';
import { MI } from '@/components/MaterialIcon';
import PageHeader from '@/components/PageHeader';

// ── 좌표 변환: map_x_m/map_y_m (미터) → SVG 픽셀 (viewBox 0 0 450 380) ──────
const SVG_W = 450;
const SVG_H = 380;
const MAP_DB_MIN_X = 0.1;
const MAP_DB_MIN_Y = 0.1;
const MAP_WIDTH_M  = 2.5;
const MAP_HEIGHT_M = 2.0;
// Mobile/Robot MapPage와 동일한 오프셋 (이미지 흰색 영역 기준)
const MAP_OFFSET = { left: 3.8462, top: 4.6512, right: 96.0385, bottom: 95.1163 };

function toSvgCoord(x_m: number, y_m: number): { x: number; y: number } {
  const innerW = (MAP_OFFSET.right  - MAP_OFFSET.left) / 100 * SVG_W;
  const innerH = (MAP_OFFSET.bottom - MAP_OFFSET.top)  / 100 * SVG_H;
  const offsetX = MAP_OFFSET.left / 100 * SVG_W;
  const offsetY = MAP_OFFSET.top  / 100 * SVG_H;

  const ratioX = (x_m - MAP_DB_MIN_X) / (MAP_WIDTH_M  - MAP_DB_MIN_X);
  const ratioY = (y_m - MAP_DB_MIN_Y) / (MAP_HEIGHT_M - MAP_DB_MIN_Y);

  return {
    x: offsetX + ratioX * innerW,
    y: offsetY + (1 - ratioY) * innerH,  // y축 반전
  };
}

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
  const { robots, zones, pois, selectedRobotId, selectRobot, triggerEStop, releaseEStop, startTeleop, sendToMaintenance, returnToStation } = useDashboard();
  const navigate = useNavigate();
  const [layers, setLayers] = useState({ robots: true, routes: true, zones: true, destinations: true });
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null);
  const selectedRobot = robots.find(r => r.id === selectedRobotId);

  // Zoom & Pan state
  const [transform, setTransform] = useState({ x: 0, y: 0, scale: 1 });
  const isPanning = useRef(false);
  const lastPan = useRef({ x: 0, y: 0 });
  const mapContainerRef = useRef<HTMLDivElement>(null);

  const MIN_SCALE = 0.5;
  const MAX_SCALE = 5;

  const clampTransform = useCallback((x: number, y: number, scale: number) => {
    return { x, y, scale: Math.min(MAX_SCALE, Math.max(MIN_SCALE, scale)) };
  }, []);

  const handleWheel = useCallback((e: WheelEvent) => {
    e.preventDefault();
    const rect = mapContainerRef.current?.getBoundingClientRect();
    if (!rect) return;
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;
    setTransform(prev => {
      const delta = e.deltaY > 0 ? 0.85 : 1.15;
      const newScale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, prev.scale * delta));
      const scaleRatio = newScale / prev.scale;
      return clampTransform(mouseX - scaleRatio * (mouseX - prev.x), mouseY - scaleRatio * (mouseY - prev.y), newScale);
    });
  }, [clampTransform]);

  useEffect(() => {
    const el = mapContainerRef.current;
    if (!el) return;
    el.addEventListener('wheel', handleWheel, { passive: false });
    return () => el.removeEventListener('wheel', handleWheel);
  }, [handleWheel]);

  const handleMouseDown = (e: React.MouseEvent) => {
    if ((e.target as Element).closest('[data-robot]')) return;
    isPanning.current = true;
    lastPan.current = { x: e.clientX, y: e.clientY };
    e.currentTarget.setAttribute('data-dragging', 'true');
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isPanning.current) return;
    const dx = e.clientX - lastPan.current.x;
    const dy = e.clientY - lastPan.current.y;
    lastPan.current = { x: e.clientX, y: e.clientY };
    setTransform(prev => clampTransform(prev.x + dx, prev.y + dy, prev.scale));
  };

  const handleMouseUp = (e: React.MouseEvent) => {
    isPanning.current = false;
    e.currentTarget.removeAttribute('data-dragging');
  };

  const handleMouseLeave = (e: React.MouseEvent) => {
    isPanning.current = false;
    e.currentTarget.removeAttribute('data-dragging');
  };

  const resetZoom = () => setTransform({ x: 0, y: 0, scale: 1 });
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
    <div className="h-[calc(100vh-4rem)] flex flex-col">
      <PageHeader title="Fleet Map" subtitle="Real-time fleet monitoring" />

      <div className="flex gap-0 flex-1 -mx-8 min-h-0 overflow-hidden">

        {/* Left: Map + Cards */}
        <div className="flex-1 flex flex-col min-h-0">

          {/* Map Area */}
          <div
            ref={mapContainerRef}
            className="flex-1 relative bg-secondary/30 overflow-hidden cursor-grab active:cursor-grabbing select-none"
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseLeave}
          >
            {/* Layer toggles */}
            <div className="absolute top-4 left-4 z-10 flex gap-2 pointer-events-auto">
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

            {/* Zoom controls */}
            <div className="absolute top-4 right-4 z-10 flex flex-col gap-1 pointer-events-auto">
              <button
                onClick={() => setTransform(prev => clampTransform(prev.x, prev.y, prev.scale * 1.25))}
                className="w-8 h-8 bg-card border border-border rounded-lg flex items-center justify-center shadow-sm hover:bg-secondary transition-colors text-sm font-bold"
              >+</button>
              <button
                onClick={() => setTransform(prev => clampTransform(prev.x, prev.y, prev.scale * 0.8))}
                className="w-8 h-8 bg-card border border-border rounded-lg flex items-center justify-center shadow-sm hover:bg-secondary transition-colors text-sm font-bold"
              >−</button>
              <button
                onClick={resetZoom}
                className="w-8 h-8 bg-card border border-border rounded-lg flex items-center justify-center shadow-sm hover:bg-secondary transition-colors"
                title="Reset zoom"
              >
                <MI icon="center_focus_strong" className="text-muted-foreground text-sm" />
              </button>
            </div>

            {/* Scale indicator */}
            <div className="absolute bottom-3 right-4 z-10 text-[10px] text-muted-foreground bg-card/80 px-2 py-1 rounded-md border border-border">
              {Math.round(transform.scale * 100)}%
            </div>

            {/* Zoomable/pannable layer */}
            <div
              className="absolute inset-0"
              style={{
                transform: `translate(${transform.x}px, ${transform.y}px) scale(${transform.scale})`,
                transformOrigin: '0 0',
                willChange: 'transform',
              }}
            >
              <svg
                className="w-full h-full"
                viewBox={`0 0 ${SVG_W} ${SVG_H}`}
                preserveAspectRatio="xMidYMid meet"
                style={{ display: 'block', width: '100%', height: '100%' }}
              >
                {/* 맵 이미지 */}
                <image
                  href="/map_end_end.png"
                  x="0" y="0"
                  width={SVG_W} height={SVG_H}
                  preserveAspectRatio="xMidYMid meet"
                  opacity="0.85"
                />

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

                {/* Routes: 운행 중인 로봇 → 목적지 POI 점선 */}
                {layers.routes && robots.filter(r => r.currentTarget && r.status === 'MOVING').map(robot => {
                  const targetPoi = pois.find(p => p.name === robot.currentTarget);
                  if (!targetPoi) return null;
                  const from = toSvgCoord(robot.position.x, robot.position.y);
                  const to   = toSvgCoord(
                    targetPoi.map_x_m ?? targetPoi.x_m,
                    targetPoi.map_y_m ?? targetPoi.y_m,
                  );
                  return (
                    <line
                      key={`route-${robot.id}`}
                      x1={from.x} y1={from.y}
                      x2={to.x}   y2={to.y}
                      stroke="hsl(239,84%,67%)"
                      strokeWidth="1.5"
                      strokeDasharray="4 4"
                      opacity="0.6"
                    />
                  );
                })}

                {/* POI Destinations — 실제 서버 데이터, map_x_m 기준 */}
                {layers.destinations && pois.map(poi => {
                  const { x, y } = toSvgCoord(
                    poi.map_x_m ?? poi.x_m,
                    poi.map_y_m ?? poi.y_m,
                  );
                  return (
                    <g key={poi.id}>
                      <rect
                        x={x - 4} y={y - 4}
                        width="8" height="8"
                        rx="2"
                        fill="hsl(var(--primary))"
                        opacity="0.85"
                      />
                      <text
                        x={x + 7} y={y + 3}
                        fontSize="7"
                        fill="#808080"
                        // className="fill-foreground"
                        style={{ fontWeight: 600 }}
                      >
                        {poi.name}
                      </text>
                    </g>
                  );
                })}

                {/* Robot markers — toSvgCoord로 미터 → SVG 변환 */}
                {layers.robots && robots.map(robot => {
                  const isSelected = robot.id === selectedRobotId;
                  const { x, y } = toSvgCoord(robot.position.x, robot.position.y);
                  const fill = robot.status === 'E_STOP'       ? '#ef4444'
                    : robot.status === 'HEADING_MAINTENANCE' || robot.status === 'HEADING_STATION' ? '#f59e0b'
                    : robot.status === 'MOVING'   ? '#3b82f6'
                    : robot.status === 'CHARGING' ? '#6366f1'
                    : '#94a3b8';
                  return (
                    <g
                      key={robot.id}
                      data-robot={robot.id}
                      className="cursor-pointer"
                      onClick={(e) => {
                        e.stopPropagation();
                        selectRobot(robot.id === selectedRobotId ? null : robot.id);
                      }}
                    >
                      {isSelected && (
                        <circle cx={x} cy={y} r="18" fill="none" stroke={fill} strokeWidth="2" opacity="0.4">
                          <animate attributeName="r" from="14" to="22" dur="1.5s" repeatCount="indefinite" />
                          <animate attributeName="opacity" from="0.4" to="0" dur="1.5s" repeatCount="indefinite" />
                        </circle>
                      )}
                      {robot.status === 'E_STOP' && (
                        <circle cx={x} cy={y} r="14" fill={fill} opacity="0.2">
                          <animate attributeName="opacity" from="0.3" to="0" dur="1s" repeatCount="indefinite" />
                        </circle>
                      )}
                      <circle cx={x} cy={y} r="8" fill={fill} stroke="white" strokeWidth="2" />
                      <text x={x} y={y - 14} textAnchor="middle" fontSize="8" fontWeight="bold" className="fill-foreground">
                        {robot.id}
                      </text>
                    </g>
                  );
                })}
              </svg>
            </div>
          </div>

          {/* Robot Cards */}
          <div className="border-t border-border bg-card/50 shrink-0">
            <div className="flex gap-3 overflow-x-auto px-4 py-3">
              {robots.map(robot => (
                <div
                  key={robot.id}
                  onClick={() => selectRobot(robot.id === selectedRobotId ? null : robot.id)}
                  className={`bg-card rounded-2xl p-3 shadow-sm border shrink-0 w-52 cursor-pointer transition-all hover:shadow-md ${
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
                  <p className="text-xs text-muted-foreground mt-1 truncate">
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
          <div className="w-96 border-l border-border bg-card p-6 overflow-y-auto shrink-0">
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

            <div className={`p-3 rounded-xl mb-4 flex items-center gap-2 ${selectedRobot.eStopActive ? 'bg-red-50 dark:bg-red-900/10 border border-red-200 dark:border-red-900/30' : 'bg-emerald-50 dark:bg-emerald-900/10 border border-emerald-200 dark:border-emerald-900/30'}`}>
              <MI icon={selectedRobot.eStopActive ? 'pan_tool' : 'check_circle'} className={selectedRobot.eStopActive ? 'text-critical-red' : 'text-emerald-500'} />
              <span className="text-sm font-bold text-foreground">E-Stop: {selectedRobot.eStopActive ? `ON (${selectedRobot.eStopSource})` : 'OFF'}</span>
            </div>

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
                onClick={() => { startTeleop(selectedRobot.id); navigate('/manual-control'); }}
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
              <button onClick={() => setPendingAction(null)} className="flex-1 py-2.5 bg-secondary text-foreground rounded-xl font-bold hover:bg-secondary/80 transition-all">
                Cancel
              </button>
              <button onClick={executeAction} className={`flex-1 py-2.5 rounded-xl font-bold active:scale-95 transition-all ${confirmConfig[pendingAction.type].confirmClass}`}>
                Confirm
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
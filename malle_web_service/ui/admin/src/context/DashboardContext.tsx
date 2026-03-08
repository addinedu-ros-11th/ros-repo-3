import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { robotApi, missionApi, eventApi, zoneApi, teleopApi, lockboxApi, poiApi, type LockboxSlotRes, type PoiRes } from '@/api/services';
import { useWsHandler } from '@/ws/useWsHandler';

export interface Robot {
  id: string;
  battery: number;
  mode: 'GUIDE' | 'FOLLOW' | 'PICKUP' | null;
  status: 'MOVING' | 'WAITING' | 'E_STOP' | 'CHARGING' | 'OFFLINE' | 'HEADING_MAINTENANCE' | 'HEADING_STATION';
  position: { x: number; y: number }; // meters (x_m, y_m)
  currentTarget: string | null;
  eta: number | null;
  sessionId: string | null;
  lastSeen: string;
  eStopActive: boolean;
  eStopSource: 'ROBOT' | 'DASHBOARD' | null;
  commsStatus: 'STRONG' | 'WEAK' | 'LOST';
  sensorStatus: 'OK' | 'FAULT';
  lockboxSlots: LockboxSlotRes[];
  route: Array<{ wp_id: string; x: number; y: number }> | null;
}

export interface Mission {
  id: string;
  robotId: string;
  sessionId: string;
  type: 'TASK' | 'TIME';
  mode: 'GUIDE' | 'FOLLOW' | 'PICKUP';
  status: 'RUNNING' | 'PAUSED' | 'COMPLETED';
  currentTarget: string;
  eta: number;
  guideQueue?: Array<{ poiName: string; status: 'PENDING' | 'ARRIVED' | 'DONE' }> | null;
}

export interface ZoneRules {
  maxSpeed?: number;
  oneWay?: boolean;
  enhancedObstacleAvoidance?: boolean;
  priority: 'LOW' | 'MEDIUM' | 'HIGH';
}

export interface Zone {
  id: string;
  name: string;
  type: 'RESTRICTED' | 'MAINTENANCE' | 'CAUTION' | 'CONGESTED';
  active: boolean;
  polygon: Array<{ x: number; y: number }>;
  rules?: ZoneRules;
}

export interface DashboardEvent {
  id: string;
  timestamp: string;
  robotId: string;
  sessionId: string | null;
  type: 'COLLISION_RISK' | 'PATH_DEVIATION' | 'LOW_BATTERY' | 'SENSOR_FAULT' | 'COMMS_LOSS' | 'ESTOP' | 'MISSION_COMPLETE' | 'LOCKBOX_OPEN';
  severity: 'INFO' | 'WARN' | 'CRITICAL';
  message: string;
  payload: Record<string, unknown>;
}

interface TeleopLog {
  timestamp: string;
  action: string;
}

interface DashboardState {
  robots: Robot[];
  missions: Mission[];
  zones: Zone[];
  events: DashboardEvent[];
  pois: PoiRes[];  // ★ 추가
  emergencyBanner: { active: boolean; message: string; robotId: string } | null;
  teleopState: { active: boolean; targetRobotId: string | null; log: TeleopLog[] };
  selectedRobotId: string | null;
  darkMode: boolean;
  expandedMissionId: string | null;
  expandedAlertId: string | null;
}

interface DashboardContextValue extends DashboardState {
  selectRobot: (id: string | null) => void;
  toggleDarkMode: () => void;
  triggerEStop: (robotId: string) => void;
  releaseEStop: (robotId: string) => void;
  stopMission: (missionId: string) => void;
  restartMission: (missionId: string) => void;
  toggleZone: (zoneId: string) => Promise<void>;
  addZone: (zone: Omit<Zone, 'id'>) => Promise<void>;
  deleteZone: (zoneId: string) => Promise<void>;
  startTeleop: (robotId: string) => void;
  stopTeleop: () => void;
  addTeleopLog: (action: string) => void;
  sendTeleopCmd: (robotId: string, linear_x: number, angular_z: number) => void;
  dismissEmergency: () => void;
  sendToMaintenance: (robotId: string) => void;
  returnToStation: (robotId: string) => void;
  setExpandedMissionId: (id: string | null) => void;
  setExpandedAlertId: (id: string | null) => void;
}

/* ───── fallback data ───── */

const initialRobots: Robot[] = [
  { id: 'R-422', battery: 82, mode: 'PICKUP', status: 'MOVING', position: { x: 120, y: 80 }, currentTarget: 'Zara Store', eta: 45, sessionId: 'S-001', lastSeen: '10:47 AM', eStopActive: false, eStopSource: null, commsStatus: 'STRONG', sensorStatus: 'OK', lockboxSlots: [] },
  { id: 'R-742', battery: 14, mode: 'FOLLOW', status: 'E_STOP', position: { x: 200, y: 150 }, currentTarget: null, eta: null, sessionId: 'S-002', lastSeen: '10:45 AM', eStopActive: true, eStopSource: 'ROBOT', commsStatus: 'WEAK', sensorStatus: 'OK', lockboxSlots: [] },
  { id: 'R-109', battery: 98, mode: 'GUIDE', status: 'WAITING', position: { x: 60, y: 200 }, currentTarget: 'Nike', eta: 0, sessionId: 'S-003', lastSeen: '10:46 AM', eStopActive: false, eStopSource: null, commsStatus: 'STRONG', sensorStatus: 'OK', lockboxSlots: [] },
  { id: 'R-305', battery: 45, mode: 'GUIDE', status: 'MOVING', position: { x: 300, y: 120 }, currentTarget: 'Apple Store', eta: 120, sessionId: 'S-004', lastSeen: '10:47 AM', eStopActive: false, eStopSource: null, commsStatus: 'STRONG', sensorStatus: 'OK', lockboxSlots: [] },
  { id: 'R-118', battery: 67, mode: 'PICKUP', status: 'MOVING', position: { x: 180, y: 250 }, currentTarget: 'Starbucks', eta: 30, sessionId: 'S-005', lastSeen: '10:47 AM', eStopActive: false, eStopSource: null, commsStatus: 'STRONG', sensorStatus: 'OK', lockboxSlots: [] },
  { id: 'R-991', battery: 5, mode: null, status: 'CHARGING', position: { x: 350, y: 300 }, currentTarget: null, eta: null, sessionId: null, lastSeen: '10:40 AM', eStopActive: false, eStopSource: null, commsStatus: 'STRONG', sensorStatus: 'OK', lockboxSlots: [] },
];

const initialMissions: Mission[] = [
  { id: 'M-001', robotId: 'R-422', sessionId: 'S-001', type: 'TIME', mode: 'PICKUP', status: 'RUNNING', currentTarget: 'Zara Store', eta: 45, guideQueue: null },
  { id: 'M-002', robotId: 'R-109', sessionId: 'S-003', type: 'TASK', mode: 'GUIDE', status: 'RUNNING', currentTarget: 'Nike', eta: 0, guideQueue: [
    { poiName: 'Nike', status: 'ARRIVED' },
    { poiName: 'Apple Store', status: 'PENDING' },
    { poiName: 'Starbucks', status: 'PENDING' },
  ]},
  { id: 'M-003', robotId: 'R-305', sessionId: 'S-004', type: 'TASK', mode: 'GUIDE', status: 'RUNNING', currentTarget: 'Apple Store', eta: 120, guideQueue: [
    { poiName: 'Apple Store', status: 'PENDING' },
    { poiName: 'H&M', status: 'PENDING' },
  ]},
  { id: 'M-004', robotId: 'R-118', sessionId: 'S-005', type: 'TIME', mode: 'PICKUP', status: 'RUNNING', currentTarget: 'Starbucks', eta: 30, guideQueue: null },
  { id: 'M-005', robotId: 'R-742', sessionId: 'S-002', type: 'TASK', mode: 'FOLLOW', status: 'PAUSED', currentTarget: 'Food Court', eta: 0, guideQueue: null },
];

const initialZones: Zone[] = [
  { id: 'Z-001', name: 'North Corridor', type: 'RESTRICTED', active: true, polygon: [{ x: 50, y: 30 }, { x: 250, y: 30 }, { x: 250, y: 80 }, { x: 50, y: 80 }] },
  { id: 'Z-002', name: 'Food Court Area', type: 'CONGESTED', active: true, polygon: [{ x: 320, y: 270 }, { x: 400, y: 270 }, { x: 400, y: 340 }, { x: 320, y: 340 }], rules: { maxSpeed: 0.2, enhancedObstacleAvoidance: true, priority: 'HIGH' } },
  { id: 'Z-003', name: 'West Wing', type: 'CAUTION', active: false, polygon: [{ x: 150, y: 200 }, { x: 280, y: 200 }, { x: 280, y: 280 }, { x: 150, y: 280 }], rules: { maxSpeed: 0.3, priority: 'MEDIUM' } },
];

const initialEvents: DashboardEvent[] = [
  { id: 'E-001', timestamp: '10:45 AM', robotId: 'R-742', sessionId: 'S-002', type: 'ESTOP', severity: 'CRITICAL', message: 'E-Stop Triggered — Obstacle detected (Hard stop)', payload: { pose: { x: 200, y: 150, heading: 90, speed: 0 } } },
  { id: 'E-002', timestamp: '10:30 AM', robotId: 'R-305', sessionId: null, type: 'PATH_DEVIATION', severity: 'WARN', message: 'Manual Intervention — Teleop active for tight corner', payload: {} },
  { id: 'E-003', timestamp: '10:15 AM', robotId: 'R-422', sessionId: 'S-001', type: 'MISSION_COMPLETE', severity: 'INFO', message: 'Mission Completed — Delivery to Zone B successful', payload: {} },
  { id: 'E-004', timestamp: '09:45 AM', robotId: 'R-742', sessionId: 'S-002', type: 'LOW_BATTERY', severity: 'WARN', message: 'Battery at 14% — Return to charging recommended', payload: {} },
  { id: 'E-005', timestamp: '09:30 AM', robotId: 'R-109', sessionId: 'S-003', type: 'MISSION_COMPLETE', severity: 'INFO', message: 'Guide session started — 3 POIs queued', payload: {} },
  { id: 'E-006', timestamp: '09:15 AM', robotId: 'R-118', sessionId: 'S-005', type: 'LOCKBOX_OPEN', severity: 'INFO', message: 'Lockbox compartment 2 opened for pickup', payload: {} },
  { id: 'E-007', timestamp: '08:55 AM', robotId: 'R-991', sessionId: null, type: 'LOW_BATTERY', severity: 'WARN', message: 'Battery critically low at 5% — Auto-docked to charging bay', payload: {} },
];

/* ───── server → frontend mapping ───── */

function mapMotionToStatus(state: Record<string, any>): Robot['status'] {
  if (state.stop_state === 'ESTOP' || state.stop_state === 'E_STOP') return 'E_STOP';
  switch (state.motion_state || state.nav_state) {
    case 'MOVING': case 'NAVIGATING': return 'MOVING';
    case 'WAITING': case 'IDLE': return 'WAITING';
    case 'CHARGING': return 'CHARGING';
    default: return 'WAITING';
  }
}

function mapModeStr(m: string | null): Robot['mode'] {
  if (!m) return null;
  const u = m.toUpperCase();
  if (u === 'GUIDE') return 'GUIDE';
  if (u === 'FOLLOW') return 'FOLLOW';
  if (u === 'PICKUP') return 'PICKUP';
  return null;
}

const DashboardContext = createContext<DashboardContextValue | null>(null);

export function DashboardProvider({ children }: { children: React.ReactNode }) {
  const [robots, setRobots] = useState<Robot[]>([]);
  const [missions, setMissions] = useState<Mission[]>([]);
  const [zones, setZones] = useState<Zone[]>([]);
  const [events, setEvents] = useState<DashboardEvent[]>([]);
  const [pois, setPois] = useState<PoiRes[]>([]);  // ★ 추가
  const [selectedRobotId, setSelectedRobotId] = useState<string | null>(null);
  const [darkMode, setDarkMode] = useState(false);
  const [expandedMissionId, setExpandedMissionId] = useState<string | null>(null);
  const [expandedAlertId, setExpandedAlertId] = useState<string | null>(null);
  const [teleopState, setTeleopState] = useState<{ active: boolean; targetRobotId: string | null; log: TeleopLog[] }>({ active: false, targetRobotId: null, log: [] });

  const hasCritical = events.some(e => e.severity === 'CRITICAL');
  const criticalEvent = events.find(e => e.severity === 'CRITICAL');
  const [emergencyDismissed, setEmergencyDismissed] = useState(false);

  const emergencyBanner = hasCritical && !emergencyDismissed && criticalEvent
    ? { active: true, message: criticalEvent.message, robotId: criticalEvent.robotId }
    : null;

  /* ───── ★ Server init (mount 시 1회) ───── */
  useEffect(() => {
    // Robots
    robotApi.list().then((res) => {
      if (!res?.robots?.length) return;
      const mapped: Robot[] = res.robots.map((r) => ({
        id: `R-${r.id}`,
        battery: r.battery_pct,
        mode: mapModeStr(r.current_mode),
        status: r.state ? mapMotionToStatus(r.state) : (r.is_online ? 'WAITING' : 'OFFLINE'),
        position: { x: r.state?.x_m ?? 0, y: r.state?.y_m ?? 0 },  // meters
        currentTarget: null,
        eta: r.state?.eta_sec ?? null,
        sessionId: null,
        lastSeen: r.last_seen_at ? new Date(r.last_seen_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'N/A',
        eStopActive: r.state?.stop_state === 'ESTOP' || r.state?.stop_state === 'E_STOP',
        eStopSource: r.state?.stop_source as Robot['eStopSource'] ?? null,
        commsStatus: r.is_online ? 'STRONG' : 'LOST',
        sensorStatus: 'OK',
        lockboxSlots: [],
        route: null,
      }));
      setRobots(mapped);
      mapped.forEach((robot) => {
        const numId = parseInt(robot.id.replace('R-', ''));
        if (!isNaN(numId)) {
          lockboxApi.getSlots(numId)
            .then((slots) => setRobots((prev) => prev.map((r) => r.id === robot.id ? { ...r, lockboxSlots: slots } : r)))
            .catch(() => {});
        }
      });
    }).catch(() => {});

    // Missions
    missionApi.list().then((res) => {
      if (!res?.length) return;
      const mapped: Mission[] = res.map((m) => ({
        id: `M-${m.id}`,
        robotId: `R-${m.robot_id}`,
        sessionId: `S-${m.session_id}`,
        type: (m.type === 'TIME' ? 'TIME' : 'TASK') as Mission['type'],
        mode: (m.type?.toUpperCase() === 'FOLLOW' ? 'FOLLOW' : m.type?.toUpperCase() === 'PICKUP' ? 'PICKUP' : 'GUIDE') as Mission['mode'],
        status: m.status === 'RUNNING' ? 'RUNNING' : m.status === 'COMPLETED' ? 'COMPLETED' : 'PAUSED',
        currentTarget: m.guide_queue?.find((g) => g.status === 'PENDING')?.poi_name || '',
        eta: 0,
        guideQueue: m.guide_queue?.map((g) => ({
          poiName: g.poi_name,
          status: g.status === 'DONE' ? 'DONE' : g.status === 'ARRIVED' ? 'ARRIVED' : 'PENDING',
        })) ?? null,
      }));
      setMissions(mapped);
    }).catch(() => {});

    // Events
    eventApi.list({ limit: 30 }).then((res) => {
      if (!res?.length) return;
      const mapped: DashboardEvent[] = res.map((e) => ({
        id: `E-${e.id}`,
        timestamp: new Date(e.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        robotId: `R-${e.robot_id}`,
        sessionId: e.session_id ? `S-${e.session_id}` : null,
        type: e.type as DashboardEvent['type'],
        severity: e.severity as DashboardEvent['severity'],
        message: `${e.type} — ${e.severity}`,
        payload: e.payload_json ?? {},
      }));
      setEvents(mapped);
    }).catch(() => {});

    // Zones
    zoneApi.list().then((res) => {
      if (!res?.length) return;
      const mapped: Zone[] = res.map((z) => ({
        id: String(z.id),
        name: z.name,
        type: (z.zone_type?.toUpperCase() || 'CAUTION') as Zone['type'],
        active: z.is_active,
        polygon: parseWkt(z.polygon_wkt),
        rules: {
          priority: (z.priority ?? 'MEDIUM') as ZoneRules['priority'],
          maxSpeed: z.speed_limit_mps ?? undefined,
          oneWay: z.one_way ?? undefined,
          enhancedObstacleAvoidance: z.enhanced_avoidance ?? undefined,
        },
      }));
      setZones(mapped);
    }).catch(() => {});

    // ★ POIs
    poiApi.list().then((res) => {
      if (!res?.length) return;
      setPois(res);
    }).catch(() => {});
  }, []);

  /* ───── ★ WS 핸들러 콜백 연결 ───── */
  const { send: wsSend } = useWsHandler({
    onRobotStateUpdated: useCallback((robotId: number, state: Record<string, any>) => {
      const rid = `R-${robotId}`;
      const nestedState = state.state as Record<string, any> | undefined;
      const x = nestedState?.x_m ?? state.x_m;
      const y = nestedState?.y_m ?? state.y_m;
      const motionOrNav = nestedState?.motion_state ?? nestedState?.nav_state ?? state.motion_state ?? state.nav_state;
      const stopState = nestedState?.stop_state ?? state.stop_state;
      const battery = state.battery_pct ?? nestedState?.battery_pct;
      const eta = nestedState?.eta_sec ?? state.eta_sec;

      setRobots(prev => prev.map(r => r.id === rid ? {
        ...r,
        ...(battery !== undefined ? { battery } : {}),
        ...(x !== undefined ? { position: { x, y: y ?? r.position.y } } : {}),  // meters
        ...(motionOrNav || stopState ? { status: mapMotionToStatus({ motion_state: motionOrNav, nav_state: motionOrNav, stop_state: stopState }) } : {}),
        ...(eta !== undefined ? { eta } : {}),
        lastSeen: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      } : r));
    }, []),

    onEStop: useCallback((robotId: number, source: string) => {
      const rid = `R-${robotId}`;
      setRobots(prev => prev.map(r => r.id === rid ? { ...r, eStopActive: true, eStopSource: (source || 'ROBOT') as Robot['eStopSource'], status: 'E_STOP' as const } : r));
      setEmergencyDismissed(false);
      setEvents(prev => [{
        id: `E-ws-${Date.now()}`, timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        robotId: rid, sessionId: null, type: 'ESTOP', severity: 'CRITICAL',
        message: `E-Stop triggered on ${rid} by ${source || 'ROBOT'}`, payload: {},
      }, ...prev].slice(0, 50));
    }, []),

    onEStopReleased: useCallback((robotId: number) => {
      const rid = `R-${robotId}`;
      setRobots(prev => prev.map(r => r.id === rid ? { ...r, eStopActive: false, eStopSource: null, status: 'WAITING' as const } : r));
    }, []),

    onMissionCreated: useCallback((data: Record<string, any>) => {
      setMissions(prev => [{
        id: `M-${data.id || Date.now()}`,
        robotId: `R-${data.robot_id}`,
        sessionId: `S-${data.session_id}`,
        type: data.type || 'TASK',
        mode: data.mode || 'GUIDE',
        status: 'RUNNING',
        currentTarget: data.current_target || '',
        eta: data.eta ?? 0,
        guideQueue: data.guide_queue ?? null,
      }, ...prev]);
    }, []),

    onMissionUpdated: useCallback((data: Record<string, any>) => {
      const mid = `M-${data.id}`;
      setMissions(prev => prev.map(m => m.id === mid ? {
        ...m,
        status: data.status === 'COMPLETED' ? 'COMPLETED' : data.status === 'PAUSED' ? 'PAUSED' : m.status,
        currentTarget: data.current_target ?? m.currentTarget,
        eta: data.eta ?? m.eta,
      } : m));
    }, []),

    onSessionAssigned: useCallback((data: Record<string, any>) => {
      const rid = `R-${data.assigned_robot_id}`;
      setRobots(prev => prev.map(r => r.id === rid ? { ...r, sessionId: `S-${data.id}` } : r));
    }, []),

    onEventReceived: useCallback((data: Record<string, any>) => {
      setEvents(prev => [{
        id: `E-${data.id || Date.now()}`,
        timestamp: data.created_at ? new Date(data.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        robotId: `R-${data.robot_id}`,
        sessionId: data.session_id ? `S-${data.session_id}` : null,
        type: data.type as DashboardEvent['type'],
        severity: data.severity as DashboardEvent['severity'],
        message: data.message || `${data.type} — ${data.severity}`,
        payload: data.payload_json ?? {},
      }, ...prev].slice(0, 50));
    }, []),

    onGuideArrived: useCallback((data: Record<string, any>) => {
      setMissions(prev => prev.map(m => {
        if (!m.guideQueue) return m;
        return {
          ...m,
          guideQueue: m.guideQueue.map(g =>
            g.poiName === data.poi_name ? { ...g, status: 'ARRIVED' as const } : g
          ),
        };
      }));
    }, []),

    onPickupStatusChanged: useCallback((data: Record<string, any>) => {
      if (data.robot_id) {
        const rid = `R-${data.robot_id}`;
        setMissions(prev => prev.map(m =>
          m.robotId === rid && m.mode === 'PICKUP'
            ? { ...m, status: data.status === 'DONE' ? 'COMPLETED' as const : m.status }
            : m
        ));
      }
    }, []),

    onLockboxOpened: useCallback((data: Record<string, any>) => {
      setEvents(prev => [{
        id: `E-lb-${Date.now()}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        robotId: `R-${data.robot_id || 'unknown'}`,
        sessionId: data.session_id ? `S-${data.session_id}` : null,
        type: 'LOCKBOX_OPEN',
        severity: 'INFO',
        message: `Lockbox slot ${data.slot_no || '?'} opened`,
        payload: data,
      }, ...prev].slice(0, 50));
    }, []),

    onLockboxUpdated: useCallback((robotId: number, slots: Record<string, any>[]) => {
      const rid = `R-${robotId}`;
      setRobots(prev => prev.map(r => r.id === rid
        ? { ...r, lockboxSlots: slots as LockboxSlotRes[] }
        : r
      ));
    }, []),

    onRouteUpdated: useCallback((robotId: number, route: Array<{ wp_id: string; x: number; y: number }>) => {
      const rid = `R-${robotId}`;
      setRobots(prev => prev.map(r => r.id === rid
        ? { ...r, route: route.length > 0 ? route : null }
        : r
      ));
    }, []),

    onFollowStarted: useCallback((data: Record<string, any>) => {
      setEvents(prev => [{
        id: `E-flw-${Date.now()}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        robotId: `R-${data.robot_id || 'unknown'}`,
        sessionId: data.session_id ? `S-${data.session_id}` : null,
        type: 'MISSION_COMPLETE',
        severity: 'INFO',
        message: `Follow mode started (tag ${data.tag_code || '?'})`,
        payload: data,
      }, ...prev].slice(0, 50));
    }, []),

    onFollowStopped: useCallback((data: Record<string, any>) => {
      setEvents(prev => [{
        id: `E-flw-${Date.now()}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        robotId: `R-${data.robot_id || 'unknown'}`,
        sessionId: data.session_id ? `S-${data.session_id}` : null,
        type: 'MISSION_COMPLETE',
        severity: 'INFO',
        message: `Follow mode stopped`,
        payload: data,
      }, ...prev].slice(0, 50));
    }, []),

    onZoneUpdated: useCallback((action: string, zone: Record<string, any>) => {
      const mapped: Zone = {
        id: String(zone.id),
        name: zone.name,
        type: zone.zone_type as Zone['type'],
        active: zone.is_active,
        polygon: parseWkt(zone.polygon_wkt),
        rules: {
          priority: (zone.priority ?? 'MEDIUM') as ZoneRules['priority'],
          maxSpeed: zone.speed_limit_mps ?? undefined,
          oneWay: zone.one_way ?? undefined,
          enhancedObstacleAvoidance: zone.enhanced_avoidance ?? undefined,
        },
      };

      if (action === 'created') {
        setZones(prev => {
          const exists = prev.some(z => z.id === mapped.id);
          return exists ? prev : [...prev, mapped];
        });
      } else if (action === 'updated') {
        setZones(prev => prev.map(z => z.id === mapped.id ? mapped : z));
      } else if (action === 'deleted') {
        setZones(prev => prev.filter(z => z.id !== String(zone.id)));
      }
    }, []),  
  });

  /* ───── Actions ───── */

  const toggleDarkMode = useCallback(() => {
    setDarkMode(prev => {
      const next = !prev;
      document.documentElement.classList.toggle('dark', next);
      return next;
    });
  }, []);

  const selectRobot = useCallback((id: string | null) => setSelectedRobotId(id), []);

  const triggerEStop = useCallback((robotId: string) => {
    setRobots(prev => prev.map(r => r.id === robotId ? { ...r, eStopActive: true, eStopSource: 'DASHBOARD', status: 'E_STOP' as const } : r));
    const numId = parseInt(robotId.replace('R-', ''));
    if (!isNaN(numId)) robotApi.triggerEStop(numId, 'DASHBOARD').catch(() => {});
  }, []);

  const releaseEStop = useCallback((robotId: string) => {
    setRobots(prev => prev.map(r => r.id === robotId ? { ...r, eStopActive: false, eStopSource: null, status: 'WAITING' as const } : r));
    const numId = parseInt(robotId.replace('R-', ''));
    if (!isNaN(numId)) robotApi.releaseEStop(numId).catch(() => {});
  }, []);

  const stopMission = useCallback((missionId: string) => {
    setMissions(prev => prev.map(m => m.id === missionId ? { ...m, status: 'PAUSED' as const } : m));
    const numId = parseInt(missionId.replace('M-', ''));
    if (!isNaN(numId)) missionApi.updateStatus(numId, 'PAUSED').catch(() => {});
  }, []);

  const restartMission = useCallback((missionId: string) => {
    setMissions(prev => prev.map(m => m.id === missionId ? { ...m, status: 'RUNNING' as const } : m));
    const numId = parseInt(missionId.replace('M-', ''));
    if (!isNaN(numId)) missionApi.updateStatus(numId, 'RUNNING').catch(() => {});
  }, []);

  const toggleZone = useCallback(async (zoneId: string) => {
    const numId = parseInt(zoneId, 10);
    if (!isNaN(numId)) {
      await zoneApi.toggle(numId);
    }
  }, []);

  const addZone = useCallback(async (zone: Omit<Zone, 'id'>) => {
    await zoneApi.create({
      name: zone.name,
      zone_type: zone.type,
      polygon_wkt: `POLYGON((${[...zone.polygon, zone.polygon[0]].map(p => `${p.x} ${p.y}`).join(', ')}))`,
      is_active: zone.active,
      priority: zone.rules?.priority ?? 'MEDIUM',
      speed_limit_mps: zone.rules?.maxSpeed ?? null,
      one_way: zone.rules?.oneWay ?? null,
      enhanced_avoidance: zone.rules?.enhancedObstacleAvoidance ?? null,
    });
  }, []);

  const deleteZone = useCallback(async (zoneId: string) => {
    const numId = parseInt(zoneId, 10);
    if (!isNaN(numId)) {
      await zoneApi.delete(numId);
    }
  }, []);

  const startTeleop = useCallback((robotId: string) => {
    setTeleopState({ active: true, targetRobotId: robotId, log: [{ timestamp: new Date().toLocaleTimeString(), action: 'TELEOP_START' }] });
    const numId = parseInt(robotId.replace('R-', ''));
    if (!isNaN(numId)) teleopApi.start(numId).catch(() => {});
  }, []);

  const stopTeleop = useCallback(() => {
    const rid = teleopState.targetRobotId;
    setTeleopState(prev => ({ ...prev, active: false, log: [...prev.log, { timestamp: new Date().toLocaleTimeString(), action: 'TELEOP_STOP' }] }));
    if (rid) {
      const numId = parseInt(rid.replace('R-', ''));
      if (!isNaN(numId)) teleopApi.stop(numId).catch(() => {});
    }
  }, [teleopState.targetRobotId]);

  const addTeleopLog = useCallback((action: string) => {
    setTeleopState(prev => ({ ...prev, log: [...prev.log, { timestamp: new Date().toLocaleTimeString(), action }] }));
  }, []);

  const sendTeleopCmd = useCallback((robotId: string, linear_x: number, angular_z: number) => {
    const numId = parseInt(robotId.replace('R-', ''));
    if (isNaN(numId)) return;
    wsSend('TELEOP_CMD', { robot_id: numId, linear_x, angular_z });
  }, [wsSend]);

  const dismissEmergency = useCallback(() => setEmergencyDismissed(true), []);

  const sendToMaintenance = useCallback((robotId: string) => {
    setRobots(prev => prev.map(r => r.id === robotId ? { ...r, status: 'HEADING_MAINTENANCE' as const, currentTarget: 'Maintenance Center', eStopActive: false, eStopSource: null } : r));
    const numId = parseInt(robotId.replace('R-', ''));
    if (!isNaN(numId)) robotApi.sendCommand(numId, 'go_maintenance').catch(() => {});
  }, []);

  const returnToStation = useCallback((robotId: string) => {
    setRobots(prev => prev.map(r => r.id === robotId ? { ...r, status: 'HEADING_STATION' as const, currentTarget: 'Home Station', eStopActive: false, eStopSource: null } : r));
    const numId = parseInt(robotId.replace('R-', ''));
    if (!isNaN(numId)) robotApi.sendCommand(numId, 'return_station').catch(() => {});
  }, []);

  return (
    <DashboardContext.Provider value={{
      robots, missions, zones, events, pois, emergencyBanner, teleopState, selectedRobotId, darkMode,
      expandedMissionId, expandedAlertId,
      selectRobot, toggleDarkMode, triggerEStop, releaseEStop, stopMission, restartMission,
      toggleZone, addZone, deleteZone, startTeleop, stopTeleop, addTeleopLog, sendTeleopCmd, dismissEmergency, sendToMaintenance, returnToStation,
      setExpandedMissionId, setExpandedAlertId,
    }}>
      {children}
    </DashboardContext.Provider>
  );
}

export function useDashboard() {
  const ctx = useContext(DashboardContext);
  if (!ctx) throw new Error('useDashboard must be used within DashboardProvider');
  return ctx;
}

/* ───── util ───── */
function parseWkt(wkt: string): Array<{ x: number; y: number }> {
  try {
    const inner = wkt.replace(/POLYGON\s*\(\(/, '').replace(/\)\)/, '');
    return inner.split(',').map(pair => {
      const [x, y] = pair.trim().split(/\s+/).map(Number);
      return { x: x || 0, y: y || 0 };
    });
  } catch {
    return [];
  }
}
import React, { createContext, useContext, useState, useCallback } from 'react';

export interface Robot {
  id: string;
  battery: number;
  mode: 'GUIDE' | 'FOLLOW' | 'PICKUP' | null;
  status: 'MOVING' | 'WAITING' | 'E_STOP' | 'CHARGING' | 'OFFLINE' | 'HEADING_MAINTENANCE' | 'HEADING_STATION';
  position: { x: number; y: number };
  currentTarget: string | null;
  eta: number | null;
  sessionId: string | null;
  lastSeen: string;
  eStopActive: boolean;
  eStopSource: 'ROBOT' | 'DASHBOARD' | null;
  commsStatus: 'STRONG' | 'WEAK' | 'LOST';
  sensorStatus: 'OK' | 'FAULT';
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
  toggleZone: (zoneId: string) => void;
  addZone: (zone: Zone) => void;
  deleteZone: (zoneId: string) => void;
  startTeleop: (robotId: string) => void;
  stopTeleop: () => void;
  addTeleopLog: (action: string) => void;
  dismissEmergency: () => void;
  sendToMaintenance: (robotId: string) => void;
  returnToStation: (robotId: string) => void;
  setExpandedMissionId: (id: string | null) => void;
  setExpandedAlertId: (id: string | null) => void;
}

const initialRobots: Robot[] = [
  { id: 'R-422', battery: 82, mode: 'PICKUP', status: 'MOVING', position: { x: 120, y: 80 }, currentTarget: 'Zara Store', eta: 45, sessionId: 'S-001', lastSeen: '10:47 AM', eStopActive: false, eStopSource: null, commsStatus: 'STRONG', sensorStatus: 'OK' },
  { id: 'R-742', battery: 14, mode: 'FOLLOW', status: 'E_STOP', position: { x: 200, y: 150 }, currentTarget: null, eta: null, sessionId: 'S-002', lastSeen: '10:45 AM', eStopActive: true, eStopSource: 'ROBOT', commsStatus: 'WEAK', sensorStatus: 'OK' },
  { id: 'R-109', battery: 98, mode: 'GUIDE', status: 'WAITING', position: { x: 60, y: 200 }, currentTarget: 'Nike', eta: 0, sessionId: 'S-003', lastSeen: '10:46 AM', eStopActive: false, eStopSource: null, commsStatus: 'STRONG', sensorStatus: 'OK' },
  { id: 'R-305', battery: 45, mode: 'GUIDE', status: 'MOVING', position: { x: 300, y: 120 }, currentTarget: 'Apple Store', eta: 120, sessionId: 'S-004', lastSeen: '10:47 AM', eStopActive: false, eStopSource: null, commsStatus: 'STRONG', sensorStatus: 'OK' },
  { id: 'R-118', battery: 67, mode: 'PICKUP', status: 'MOVING', position: { x: 180, y: 250 }, currentTarget: 'Starbucks', eta: 30, sessionId: 'S-005', lastSeen: '10:47 AM', eStopActive: false, eStopSource: null, commsStatus: 'STRONG', sensorStatus: 'OK' },
  { id: 'R-991', battery: 5, mode: null, status: 'CHARGING', position: { x: 350, y: 300 }, currentTarget: null, eta: null, sessionId: null, lastSeen: '10:40 AM', eStopActive: false, eStopSource: null, commsStatus: 'STRONG', sensorStatus: 'OK' },
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

const DashboardContext = createContext<DashboardContextValue | null>(null);

export function DashboardProvider({ children }: { children: React.ReactNode }) {
  const [robots, setRobots] = useState<Robot[]>(initialRobots);
  const [missions, setMissions] = useState<Mission[]>(initialMissions);
  const [zones, setZones] = useState<Zone[]>(initialZones);
  const [events] = useState<DashboardEvent[]>(initialEvents);
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
  }, []);

  const releaseEStop = useCallback((robotId: string) => {
    setRobots(prev => prev.map(r => r.id === robotId ? { ...r, eStopActive: false, eStopSource: null, status: 'WAITING' as const } : r));
  }, []);

  const stopMission = useCallback((missionId: string) => {
    setMissions(prev => prev.map(m => m.id === missionId ? { ...m, status: 'PAUSED' as const } : m));
  }, []);

  const restartMission = useCallback((missionId: string) => {
    setMissions(prev => prev.map(m => m.id === missionId ? { ...m, status: 'RUNNING' as const } : m));
  }, []);

  const toggleZone = useCallback((zoneId: string) => {
    setZones(prev => prev.map(z => z.id === zoneId ? { ...z, active: !z.active } : z));
    // TODO: Connect to backend — syncs with DB and ROS2 costmap
    try { fetch(`/api/zones/${zoneId}/toggle`, { method: 'PATCH' }).catch(() => {}); } catch {}
  }, []);

  const addZone = useCallback((zone: Zone) => {
    setZones(prev => [...prev, zone]);
    // TODO: Connect to backend — syncs with DB and ROS2 costmap
    try { fetch('/api/zones', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(zone) }).catch(() => {}); } catch {}
  }, []);

  const deleteZone = useCallback((zoneId: string) => {
    setZones(prev => prev.filter(z => z.id !== zoneId));
    // TODO: Connect to backend — syncs with DB and ROS2 costmap
    try { fetch(`/api/zones/${zoneId}`, { method: 'DELETE' }).catch(() => {}); } catch {}
  }, []);

  const startTeleop = useCallback((robotId: string) => {
    setTeleopState({ active: true, targetRobotId: robotId, log: [{ timestamp: new Date().toLocaleTimeString(), action: 'TELEOP_START' }] });
  }, []);

  const stopTeleop = useCallback(() => {
    setTeleopState(prev => ({ ...prev, active: false, log: [...prev.log, { timestamp: new Date().toLocaleTimeString(), action: 'TELEOP_STOP' }] }));
  }, []);

  const addTeleopLog = useCallback((action: string) => {
    setTeleopState(prev => ({ ...prev, log: [...prev.log, { timestamp: new Date().toLocaleTimeString(), action }] }));
  }, []);

  const dismissEmergency = useCallback(() => setEmergencyDismissed(true), []);

  const sendToMaintenance = useCallback((robotId: string) => {
    setRobots(prev => prev.map(r => r.id === robotId ? { ...r, status: 'HEADING_MAINTENANCE' as const, currentTarget: 'Maintenance Center', eStopActive: false, eStopSource: null } : r));
  }, []);

  const returnToStation = useCallback((robotId: string) => {
    setRobots(prev => prev.map(r => r.id === robotId ? { ...r, status: 'HEADING_STATION' as const, currentTarget: 'Home Station', eStopActive: false, eStopSource: null } : r));
  }, []);

  return (
    <DashboardContext.Provider value={{
      robots, missions, zones, events, emergencyBanner, teleopState, selectedRobotId, darkMode,
      expandedMissionId, expandedAlertId,
      selectRobot, toggleDarkMode, triggerEStop, releaseEStop, stopMission, restartMission,
      toggleZone, addZone, deleteZone, startTeleop, stopTeleop, addTeleopLog, dismissEmergency, sendToMaintenance, returnToStation,
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

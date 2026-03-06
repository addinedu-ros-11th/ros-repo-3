import { useState, useCallback, useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { useDashboard } from '@/context/DashboardContext';
import { MI } from '@/components/MaterialIcon';
import PageHeader from '@/components/PageHeader';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function toNumericId(id: string): number | null {
  const n = parseInt(id.replace(/^R-/, ''), 10);
  return isNaN(n) ? null : n;
}

function streamUrl(robotId: number) {
  return `${API_BASE}/api/v1/robots/${robotId}/camera/stream`;
}

const DIR_VELOCITIES: Record<string, { linear_x: number; angular_z: number }> = {
  FWD:   { linear_x: 0.3,  angular_z:  0.0 },
  BWD:   { linear_x: -0.3, angular_z:  0.0 },
  LEFT:  { linear_x: 0.0,  angular_z:  0.5 },
  RIGHT: { linear_x: 0.0,  angular_z: -0.5 },
};

export default function ManualControlPage() {
  const { robots, teleopState, startTeleop, stopTeleop, addTeleopLog, sendTeleopCmd, triggerEStop, releaseEStop } = useDashboard();
  const location = useLocation();
  const navRobotId = (location.state as { robotId?: string })?.robotId;
  const [selectedBotId, setSelectedBotId] = useState(navRobotId || teleopState.targetRobotId || robots[0]?.id || '');
  const selectedBot = robots.find(r => r.id === selectedBotId);
  const [moving, setMoving] = useState<string | null>(null);
  const [camLoading, setCamLoading] = useState(false);
  const [camError, setCamError] = useState(false);
  const cmdIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // 로봇 변경 시 카메라 에러 리셋
  useEffect(() => {
    setCamError(false);
    setCamLoading(false);
  }, [selectedBotId]);

  const handleSelect = (id: string) => {
    setSelectedBotId(id);
    if (teleopState.active) {
      stopTeleop();
    }
  };

  const toggleTeleop = () => {
    if (teleopState.active) {
      stopTeleop();
    } else {
      startTeleop(selectedBotId);
    }
  };

  const handleDirection = useCallback((dir: string, isDown: boolean) => {
    if (!teleopState.active) return;
    if (isDown) {
      setMoving(dir);
      addTeleopLog(`MOVE_${dir.toUpperCase()}`);
      if (cmdIntervalRef.current) clearInterval(cmdIntervalRef.current);
      const vel = DIR_VELOCITIES[dir];
      const targetId = teleopState.targetRobotId || selectedBotId;
      sendTeleopCmd(targetId, vel.linear_x, vel.angular_z);
      cmdIntervalRef.current = setInterval(() => {
        sendTeleopCmd(targetId, vel.linear_x, vel.angular_z);
      }, 100);
    } else {
      setMoving(null);
      if (cmdIntervalRef.current) { clearInterval(cmdIntervalRef.current); cmdIntervalRef.current = null; }
      sendTeleopCmd(teleopState.targetRobotId || selectedBotId, 0.0, 0.0);
    }
  }, [teleopState.active, teleopState.targetRobotId, selectedBotId, addTeleopLog, sendTeleopCmd]);

  const handleStop = useCallback(() => {
    setMoving(null);
    if (cmdIntervalRef.current) { clearInterval(cmdIntervalRef.current); cmdIntervalRef.current = null; }
    addTeleopLog('STOP');
    sendTeleopCmd(teleopState.targetRobotId || selectedBotId, 0.0, 0.0);
  }, [teleopState.targetRobotId, selectedBotId, addTeleopLog, sendTeleopCmd]);

  // 언마운트 시 interval 정리
  useEffect(() => {
    return () => { if (cmdIntervalRef.current) clearInterval(cmdIntervalRef.current); };
  }, []);

  // Keyboard support
  useEffect(() => {
    const keyMap: Record<string, string> = { ArrowUp: 'FWD', ArrowDown: 'BWD', ArrowLeft: 'LEFT', ArrowRight: 'RIGHT' };
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.repeat) return;
      if (keyMap[e.key]) { e.preventDefault(); handleDirection(keyMap[e.key], true); }
      if (e.key === ' ') { e.preventDefault(); handleStop(); }
    };
    const handleKeyUp = (e: KeyboardEvent) => {
      if (keyMap[e.key]) handleDirection(keyMap[e.key], false);
    };
    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    return () => { window.removeEventListener('keydown', handleKeyDown); window.removeEventListener('keyup', handleKeyUp); };
  }, [handleDirection, handleStop]);

  const handleEStop = () => {
    if (selectedBot) {
      if (selectedBot.eStopActive) releaseEStop(selectedBot.id);
      else triggerEStop(selectedBot.id);
    }
  };

  return (
    <div>
      <PageHeader title="Manual Control" subtitle="Direct teleoperation interface" />

      <div className="flex gap-6 h-[calc(100vh-14rem)]">
        {/* Main Area */}
        <div className="flex-1 flex flex-col gap-4">
          {/* Top bar */}
          <div className="flex items-center gap-4">
            <select
              value={selectedBotId}
              onChange={e => handleSelect(e.target.value)}
              className="rounded-xl border border-border bg-card px-4 py-2.5 text-foreground text-sm font-medium"
            >
              {robots.map(r => (
                <option key={r.id} value={r.id}>{r.id} — {r.status}</option>
              ))}
            </select>
            <button
              onClick={toggleTeleop}
              className={`flex items-center gap-2 px-4 py-2 rounded-full text-sm font-bold transition-all ${
                teleopState.active ? 'bg-emerald-500 text-primary-foreground' : 'bg-secondary text-muted-foreground'
              }`}
            >
              {teleopState.active && <div className="w-2 h-2 bg-primary-foreground rounded-full animate-ping" />}
              Teleop: {teleopState.active ? 'ON' : 'OFF'}
            </button>
          </div>

          {/* Camera feed */}
          <div className="flex-1 bg-black rounded-3xl relative overflow-hidden">
            {toNumericId(selectedBotId) !== null && (
              <img
                key={selectedBotId}
                src={streamUrl(toNumericId(selectedBotId)!)}
                alt={`Robot ${selectedBotId} camera`}
                className="w-full h-full object-contain"
                onLoad={() => setCamLoading(false)}
                onError={() => { setCamLoading(false); setCamError(true); }}
              />
            )}

            {/* 오버레이: 로딩 */}
            {camLoading && !camError && (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-black/80">
                <MI icon="videocam" className="text-muted-foreground/40 text-7xl animate-pulse" />
                <p className="text-muted-foreground/60 text-sm">Waiting for camera stream…</p>
              </div>
            )}

            {/* 오버레이: 에러 */}
            {camError && (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-black/80">
                <MI icon="videocam_off" className="text-red-400/60 text-7xl" />
                <p className="text-red-400/80 text-sm font-medium">Camera unavailable</p>
                <p className="text-muted-foreground/40 text-xs">bridge_node offline or no frames received</p>
                <button
                  onClick={() => { setCamError(false); setCamLoading(true); }}
                  className="mt-2 px-4 py-2 rounded-xl bg-card/80 text-foreground text-xs font-medium hover:bg-card transition-colors"
                >
                  Retry
                </button>
              </div>
            )}

            {/* 좌하단: 로봇 ID 워터마크 */}
            {!camError && !camLoading && (
              <div className="absolute bottom-4 left-4 px-3 py-1 bg-black/50 rounded-lg text-white text-xs font-mono">
                {selectedBotId}
              </div>
            )}

            {moving && (
              <div className="absolute top-4 left-1/2 -translate-x-1/2 bg-primary text-primary-foreground px-4 py-2 rounded-full text-sm font-bold animate-pulse">
                MOVING: {moving}
              </div>
            )}

            {/* D-pad controls */}
            {teleopState.active && (
              <div className="absolute bottom-8 left-1/2 -translate-x-1/2 grid grid-cols-3 gap-2 w-56 place-items-center">
                <div />
                <button
                  onMouseDown={() => handleDirection('FWD', true)}
                  onMouseUp={() => handleDirection('FWD', false)}
                  onMouseLeave={() => handleDirection('FWD', false)}
                  onTouchStart={(e) => { e.preventDefault(); handleDirection('FWD', true); }}
                  onTouchEnd={(e) => { e.preventDefault(); handleDirection('FWD', false); }}
                  className={`w-16 h-16 rounded-2xl shadow-lg flex items-center justify-center transition-all ${
                    moving === 'FWD' ? 'bg-primary text-primary-foreground scale-90' : 'bg-card/90 backdrop-blur text-foreground active:scale-90'
                  }`}
                >
                  <MI icon="arrow_upward" className="text-2xl" />
                </button>
                <div />

                <button
                  onMouseDown={() => handleDirection('LEFT', true)}
                  onMouseUp={() => handleDirection('LEFT', false)}
                  onMouseLeave={() => handleDirection('LEFT', false)}
                  onTouchStart={(e) => { e.preventDefault(); handleDirection('LEFT', true); }}
                  onTouchEnd={(e) => { e.preventDefault(); handleDirection('LEFT', false); }}
                  className={`w-16 h-16 rounded-2xl shadow-lg flex items-center justify-center transition-all ${
                    moving === 'LEFT' ? 'bg-primary text-primary-foreground scale-90' : 'bg-card/90 backdrop-blur text-foreground active:scale-90'
                  }`}
                >
                  <MI icon="arrow_back" className="text-2xl" />
                </button>
                <button
                  onMouseDown={handleStop}
                  onTouchStart={(e) => { e.preventDefault(); handleStop(); }}
                  className="w-16 h-16 bg-critical-red text-primary-foreground rounded-2xl shadow-lg flex items-center justify-center active:scale-90 transition-all"
                >
                  <MI icon="stop" className="text-2xl" />
                </button>
                <button
                  onMouseDown={() => handleDirection('RIGHT', true)}
                  onMouseUp={() => handleDirection('RIGHT', false)}
                  onMouseLeave={() => handleDirection('RIGHT', false)}
                  onTouchStart={(e) => { e.preventDefault(); handleDirection('RIGHT', true); }}
                  onTouchEnd={(e) => { e.preventDefault(); handleDirection('RIGHT', false); }}
                  className={`w-16 h-16 rounded-2xl shadow-lg flex items-center justify-center transition-all ${
                    moving === 'RIGHT' ? 'bg-primary text-primary-foreground scale-90' : 'bg-card/90 backdrop-blur text-foreground active:scale-90'
                  }`}
                >
                  <MI icon="arrow_forward" className="text-2xl" />
                </button>

                <div />
                <button
                  onMouseDown={() => handleDirection('BWD', true)}
                  onMouseUp={() => handleDirection('BWD', false)}
                  onMouseLeave={() => handleDirection('BWD', false)}
                  onTouchStart={(e) => { e.preventDefault(); handleDirection('BWD', true); }}
                  onTouchEnd={(e) => { e.preventDefault(); handleDirection('BWD', false); }}
                  className={`w-16 h-16 rounded-2xl shadow-lg flex items-center justify-center transition-all ${
                    moving === 'BWD' ? 'bg-primary text-primary-foreground scale-90' : 'bg-card/90 backdrop-blur text-foreground active:scale-90'
                  }`}
                >
                  <MI icon="arrow_downward" className="text-2xl" />
                </button>
                <div />
              </div>
            )}
          </div>

          {/* Teleop Log */}
          <div className="bg-card rounded-2xl p-4 border border-border h-40 overflow-auto">
            <h4 className="text-sm font-bold text-foreground mb-2">Teleop Log</h4>
            <table className="w-full text-xs">
              <thead>
                <tr className="text-muted-foreground uppercase tracking-wider">
                  <th className="text-left pb-2 font-semibold">Time</th>
                  <th className="text-left pb-2 font-semibold">Action</th>
                  <th className="text-left pb-2 font-semibold">Source</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {[...teleopState.log].reverse().slice(0, 10).map((log, i) => (
                  <tr key={i}>
                    <td className="py-1.5 text-muted-foreground">{log.timestamp}</td>
                    <td className="py-1.5 font-mono font-bold text-foreground">{log.action}</td>
                    <td className="py-1.5 text-muted-foreground">DASHBOARD</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right panel */}
        <div className="w-80 flex flex-col gap-4">
          {/* Robot Status */}
          <div className="bg-card rounded-3xl p-6 border border-border flex-1">
            <h4 className="text-sm font-bold text-foreground mb-4 uppercase tracking-wider">Robot Status</h4>
            {selectedBot && (
              <div className="space-y-3">
                {[
                  { label: 'State', value: selectedBot.status.replace('_', '-'), icon: 'info' },
                  { label: 'Comms', value: selectedBot.commsStatus, icon: 'wifi' },
                  { label: 'Sensors', value: selectedBot.sensorStatus, icon: 'sensors' },
                  { label: 'Battery', value: `${selectedBot.battery}%`, icon: 'battery_full' },
                  { label: 'Speed', value: moving ? '0.8 m/s' : '0.0 m/s', icon: 'speed' },
                ].map(item => (
                  <div key={item.label} className="flex items-center gap-3 p-2 rounded-xl">
                    <MI icon={item.icon} className="text-muted-foreground text-lg" />
                    <div className="flex-1">
                      <p className="text-xs text-muted-foreground">{item.label}</p>
                      <p className="text-sm font-bold text-foreground">{item.value}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* E-Stop button */}
            <button
              onClick={handleEStop}
              className={`w-full py-4 rounded-2xl text-lg font-bold shadow-xl active:scale-95 transition-all mt-6 flex items-center justify-center gap-2 ${
                selectedBot?.eStopActive
                  ? 'bg-emerald-500 text-primary-foreground'
                  : 'bg-critical-red text-primary-foreground'
              }`}
            >
              <MI icon={selectedBot?.eStopActive ? 'play_circle' : 'emergency'} className="text-2xl" />
              {selectedBot?.eStopActive ? 'RESUME' : 'E-STOP'}
            </button>
          </div>

          {/* Lockbox */}
          <div className="bg-card rounded-2xl p-4 border border-border">
            <h4 className="text-xs font-bold text-foreground mb-2 uppercase tracking-wider">Lockbox Status</h4>
            <div className="flex gap-2 mb-3">
              {(selectedBot?.lockboxSlots?.length
                ? selectedBot.lockboxSlots
                : [1, 2, 3, 4, 5].map(i => ({ slot_no: i, status: 'EMPTY' }))
              ).map(sl => (
                <div
                  key={sl.slot_no}
                  title={`Slot ${sl.slot_no}: ${sl.status}`}
                  className={`w-6 h-6 rounded-full border-2 ${
                    sl.status === 'EMPTY'
                      ? 'bg-secondary border-border'
                      : sl.status === 'RESERVED'
                      ? 'bg-amber-400 border-amber-500'
                      : 'bg-emerald-500 border-emerald-600'
                  }`}
                />
              ))}
            </div>
            <p className="text-xs text-muted-foreground">
              {selectedBot?.lockboxSlots?.length
                ? `${selectedBot.lockboxSlots.filter(s => s.status !== 'EMPTY').length} occupied • ${selectedBot.lockboxSlots.filter(s => s.status === 'EMPTY').length} available`
                : 'Loading...'}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

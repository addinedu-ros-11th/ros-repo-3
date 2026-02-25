import { useState, useCallback, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { useDashboard } from '@/context/DashboardContext';
import { MI } from '@/components/MaterialIcon';
import PageHeader from '@/components/PageHeader';

export default function ManualControlPage() {
  const { robots, teleopState, startTeleop, stopTeleop, addTeleopLog, triggerEStop, releaseEStop } = useDashboard();
  const location = useLocation();
  const navRobotId = (location.state as { robotId?: string })?.robotId;
  const [selectedBotId, setSelectedBotId] = useState(navRobotId || teleopState.targetRobotId || robots[0]?.id || '');
  const selectedBot = robots.find(r => r.id === selectedBotId);
  const [moving, setMoving] = useState<string | null>(null);

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
    } else {
      setMoving(null);
      addTeleopLog('STOP');
    }
  }, [teleopState.active, addTeleopLog]);

  const handleStop = () => {
    setMoving(null);
    addTeleopLog('STOP');
  };

  // Keyboard support
  useEffect(() => {
    const keyMap: Record<string, string> = { ArrowUp: 'FWD', ArrowDown: 'BWD', ArrowLeft: 'LEFT', ArrowRight: 'RIGHT' };
    const handleKeyDown = (e: KeyboardEvent) => {
      if (keyMap[e.key]) { e.preventDefault(); handleDirection(keyMap[e.key], true); }
      if (e.key === ' ') { e.preventDefault(); handleStop(); }
    };
    const handleKeyUp = (e: KeyboardEvent) => {
      if (keyMap[e.key]) handleDirection(keyMap[e.key], false);
    };
    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    return () => { window.removeEventListener('keydown', handleKeyDown); window.removeEventListener('keyup', handleKeyUp); };
  }, [handleDirection]);

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
          <div className="flex-1 bg-foreground/90 rounded-3xl flex items-center justify-center relative overflow-hidden">
            <div className="text-center">
              <MI icon="videocam" className="text-muted-foreground/40 text-7xl" />
              <p className="text-muted-foreground/40 text-sm mt-2">Camera Feed — Demo Mode</p>
            </div>
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
                  onMouseLeave={() => moving === 'FWD' && handleDirection('FWD', false)}
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
                  onMouseLeave={() => moving === 'LEFT' && handleDirection('LEFT', false)}
                  className={`w-16 h-16 rounded-2xl shadow-lg flex items-center justify-center transition-all ${
                    moving === 'LEFT' ? 'bg-primary text-primary-foreground scale-90' : 'bg-card/90 backdrop-blur text-foreground active:scale-90'
                  }`}
                >
                  <MI icon="arrow_back" className="text-2xl" />
                </button>
                <button
                  onClick={handleStop}
                  className="w-16 h-16 bg-critical-red text-primary-foreground rounded-2xl shadow-lg flex items-center justify-center active:scale-90 transition-all"
                >
                  <MI icon="stop" className="text-2xl" />
                </button>
                <button
                  onMouseDown={() => handleDirection('RIGHT', true)}
                  onMouseUp={() => handleDirection('RIGHT', false)}
                  onMouseLeave={() => moving === 'RIGHT' && handleDirection('RIGHT', false)}
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
                  onMouseLeave={() => moving === 'BWD' && handleDirection('BWD', false)}
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
          <div className="bg-card rounded-2xl p-4 border border-border max-h-40 overflow-auto">
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
              {[1, 2, 3, 4, 5].map(i => (
                <div key={i} className={`w-6 h-6 rounded-full border-2 ${i <= 2 ? 'bg-emerald-500 border-emerald-600' : 'bg-secondary border-border'}`} />
              ))}
            </div>
            <p className="text-xs text-muted-foreground">Slots 1-2 occupied • 3 available</p>
          </div>
        </div>
      </div>
    </div>
  );
}

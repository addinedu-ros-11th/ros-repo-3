import { useState, useEffect } from 'react';
import { useDashboard } from '@/context/DashboardContext';
import { MI } from '@/components/MaterialIcon';
import PageHeader from '@/components/PageHeader';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

/** "R-3" → 3  (변환 실패 시 null) */
function toNumericId(id: string): number | null {
  const n = parseInt(id.replace(/^R-/, ''), 10);
  return isNaN(n) ? null : n;
}

function streamUrl(robotId: number) {
  return `${API_BASE}/api/v1/robots/${robotId}/camera/stream`;
}

export default function CameraPage() {
  const { robots } = useDashboard();
  const [selectedRobotId, setSelectedRobotId] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  // 첫 로봇 자동 선택
  useEffect(() => {
    if (robots.length > 0 && !selectedRobotId) {
      setSelectedRobotId(robots[0].id);
    }
  }, [robots, selectedRobotId]);

  // 로봇 변경 시 에러 리셋
  useEffect(() => {
    setError(false);
  }, [selectedRobotId]);

  const numericId = toNumericId(selectedRobotId);
  const selectedRobot = robots.find(r => r.id === selectedRobotId);

  return (
    <div>
      <PageHeader title="Camera Feed" subtitle="Real-time robot camera stream" />

      <div className="flex flex-col gap-4">
        {/* 로봇 선택 + 상태 */}
        <div className="flex items-center gap-4 flex-wrap">
          <label className="text-sm font-medium text-muted-foreground">Robot</label>
          <select
            value={selectedRobotId}
            onChange={e => setSelectedRobotId(e.target.value)}
            className="rounded-xl border border-border bg-card px-4 py-2.5 text-foreground text-sm font-medium"
          >
            {robots.map(r => (
              <option key={r.id} value={r.id}>
                {r.id} — {r.status}
              </option>
            ))}
          </select>

          {/* 스트림 상태 뱃지 */}
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-bold ${
            error
              ? 'bg-red-500/20 text-red-400'
              : loading
              ? 'bg-amber-500/20 text-amber-400'
              : 'bg-emerald-500/20 text-emerald-400'
          }`}>
            <div className={`w-2 h-2 rounded-full ${
              error ? 'bg-red-400' : loading ? 'bg-amber-400 animate-pulse' : 'bg-emerald-400 animate-ping'
            }`} />
            {error ? 'No Signal' : loading ? 'Connecting…' : 'Live'}
          </div>

          {/* 배터리 표시 */}
          {selectedRobot && (
            <span className="text-xs text-muted-foreground">
              Battery: {selectedRobot.battery}%
            </span>
          )}
        </div>

        {/* 스트림 화면 */}
        <div
          className="relative bg-black rounded-3xl overflow-hidden w-full"
          style={{ aspectRatio: '4/3', maxHeight: '70vh' }}
        >
          {numericId !== null && (
            <img
              key={numericId}   /* 로봇 변경 시 img 완전 재마운트 */
              src={streamUrl(numericId)}
              alt={`Robot ${selectedRobotId} camera`}
              className="w-full h-full object-contain"
              onLoad={() => setLoading(false)}
              onError={() => { setLoading(false); setError(true); }}
            />
          )}

          {/* 오버레이: 로딩 */}
          {loading && !error && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-black/80">
              <MI icon="videocam" className="text-muted-foreground/40 text-7xl animate-pulse" />
              <p className="text-muted-foreground/60 text-sm">Waiting for camera stream…</p>
            </div>
          )}

          {/* 오버레이: 에러 */}
          {error && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-black/80">
              <MI icon="videocam_off" className="text-red-400/60 text-7xl" />
              <p className="text-red-400/80 text-sm font-medium">Camera unavailable</p>
              <p className="text-muted-foreground/40 text-xs">bridge_node offline or no frames received</p>
              <button
                onClick={() => { setError(false); setLoading(true); }}
                className="mt-2 px-4 py-2 rounded-xl bg-card/80 text-foreground text-xs font-medium hover:bg-card transition-colors"
              >
                Retry
              </button>
            </div>
          )}

          {/* 좌하단: 로봇 ID 워터마크 */}
          {!error && !loading && (
            <div className="absolute bottom-4 left-4 px-3 py-1 bg-black/50 rounded-lg text-white text-xs font-mono">
              {selectedRobotId}
            </div>
          )}
        </div>

        {/* 스트림 URL 힌트 */}
        {numericId !== null && (
          <p className="text-xs text-muted-foreground">
            Stream URL:&nbsp;
            <code className="font-mono bg-secondary px-1.5 py-0.5 rounded">
              {streamUrl(numericId)}
            </code>
          </p>
        )}
      </div>
    </div>
  );
}

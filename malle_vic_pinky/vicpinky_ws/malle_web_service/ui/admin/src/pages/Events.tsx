import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDashboard } from '@/context/DashboardContext';
import { MI } from '@/components/MaterialIcon';
import PageHeader from '@/components/PageHeader';

const severityBadge: Record<string, string> = {
  INFO: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  WARN: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  CRITICAL: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
};

const severities = ['ALL', 'INFO', 'WARN', 'CRITICAL'] as const;
const timeRanges = ['1h', '24h', '7d', 'All'] as const;

export default function EventsPage() {
  const { events, robots, selectRobot, expandedAlertId, setExpandedAlertId } = useDashboard();
  const navigate = useNavigate();
  const [severityFilter, setSeverityFilter] = useState<string>('ALL');
  const [robotFilter, setRobotFilter] = useState<string>('All');
  const [timeFilter, setTimeFilter] = useState<string>('All');
  const [expanded, setExpanded] = useState<string | null>(null);
  const [highlightId, setHighlightId] = useState<string | null>(null);
  const rowRefs = useRef<Record<string, HTMLTableRowElement | null>>({});

  useEffect(() => {
    if (expandedAlertId) {
      setExpanded(expandedAlertId);
      setHighlightId(expandedAlertId);
      setTimeout(() => {
        rowRefs.current[expandedAlertId]?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, 100);
      setExpandedAlertId(null);
      setTimeout(() => setHighlightId(null), 2000);
    }
  }, [expandedAlertId, setExpandedAlertId]);

  const filtered = events.filter(e => {
    if (severityFilter !== 'ALL' && e.severity !== severityFilter) return false;
    if (robotFilter !== 'All' && e.robotId !== robotFilter) return false;
    return true;
  });

  return (
    <div>
      <PageHeader title="Event Log" subtitle="System-wide event monitoring" />

      {/* Filters */}
      <div className="flex items-center gap-4 mb-6 flex-wrap">
        <select
          value={robotFilter}
          onChange={e => setRobotFilter(e.target.value)}
          className="rounded-xl border border-border bg-card px-4 py-2 text-sm text-foreground"
        >
          <option value="All">All Robots</option>
          {robots.map(r => (
            <option key={r.id} value={r.id}>{r.id}</option>
          ))}
        </select>

        <div className="flex gap-1">
          {severities.map(s => (
            <button
              key={s}
              onClick={() => setSeverityFilter(s)}
              className={`px-3 py-1.5 rounded-full text-xs font-bold transition-all ${
                severityFilter === s
                  ? s === 'CRITICAL' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                  : s === 'WARN' ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'
                  : s === 'INFO' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
                  : 'bg-primary text-primary-foreground'
                  : 'bg-card border border-border text-muted-foreground'
              }`}
            >
              {s}
            </button>
          ))}
        </div>

        <div className="flex gap-1">
          {timeRanges.map(t => (
            <button
              key={t}
              onClick={() => setTimeFilter(t)}
              className={`px-3 py-1.5 rounded-full text-xs font-bold transition-all ${
                timeFilter === t ? 'bg-primary text-primary-foreground' : 'bg-card border border-border text-muted-foreground'
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {/* Events Table */}
      <div className="bg-card rounded-3xl p-6 shadow-sm border border-border">
        <table className="w-full">
          <thead>
            <tr className="text-left text-muted-foreground text-xs uppercase tracking-wider">
              <th className="pb-4 font-semibold">Timestamp</th>
              <th className="pb-4 font-semibold">Robot</th>
              <th className="pb-4 font-semibold">Session</th>
              <th className="pb-4 font-semibold">Type</th>
              <th className="pb-4 font-semibold">Severity</th>
              <th className="pb-4 font-semibold">Message</th>
              <th className="pb-4 font-semibold">Map</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {filtered.map(event => (
              <>
                <tr
                  key={event.id}
                  ref={el => { rowRefs.current[event.id] = el; }}
                  className={`group hover:bg-secondary/50 transition-all cursor-pointer ${highlightId === event.id ? 'ring-2 ring-primary' : ''}`}
                  onClick={() => setExpanded(expanded === event.id ? null : event.id)}
                >
                  <td className="py-4 text-sm text-muted-foreground whitespace-nowrap">{event.timestamp}</td>
                  <td className="py-4 text-sm font-bold text-foreground">{event.robotId}</td>
                  <td className="py-4 text-sm text-muted-foreground">{event.sessionId || '—'}</td>
                  <td className="py-4">
                    <span className="text-xs font-mono font-bold text-foreground">{event.type}</span>
                  </td>
                  <td className="py-4">
                    <span className={`text-xs font-bold px-3 py-1 rounded-full ${severityBadge[event.severity]}`}>{event.severity}</span>
                  </td>
                  <td className="py-4 text-sm text-foreground max-w-xs truncate">{event.message}</td>
                  <td className="py-4">
                    <button
                      onClick={e => {
                        e.stopPropagation();
                        selectRobot(event.robotId);
                        navigate('/fleet-map');
                      }}
                      className="p-1.5 rounded-lg hover:bg-secondary text-primary transition-colors"
                      title="View on map"
                    >
                      <MI icon="map" className="text-lg" />
                    </button>
                  </td>
                </tr>
                {expanded === event.id && (
                  <tr key={`${event.id}-detail`}>
                    <td colSpan={7} className="pb-4">
                      <div className="bg-secondary/50 rounded-xl p-4 ml-4">
                        <pre className="text-xs font-mono text-foreground whitespace-pre-wrap">
                          {JSON.stringify(event.payload, null, 2)}
                        </pre>
                      </div>
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

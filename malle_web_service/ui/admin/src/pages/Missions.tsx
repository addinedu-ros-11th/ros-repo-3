import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDashboard } from '@/context/DashboardContext';
import { MI } from '@/components/MaterialIcon';
import PageHeader from '@/components/PageHeader';
import { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider } from '@/components/ui/tooltip';

const statusBadge: Record<string, string> = {
  RUNNING: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
  PAUSED: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  COMPLETED: 'bg-secondary text-muted-foreground',
};

const modeBadge: Record<string, string> = {
  GUIDE: 'bg-secondary text-muted-foreground',
  FOLLOW: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  PICKUP: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
};

export default function MissionsPage() {
  const { missions, stopMission, restartMission, expandedMissionId, setExpandedMissionId, selectRobot } = useDashboard();
  const navigate = useNavigate();
  const [expanded, setExpanded] = useState<string | null>(null);
  const [highlightId, setHighlightId] = useState<string | null>(null);
  const rowRefs = useRef<Record<string, HTMLTableRowElement | null>>({});

  useEffect(() => {
    if (expandedMissionId) {
      setExpanded(expandedMissionId);
      setHighlightId(expandedMissionId);
      setTimeout(() => {
        rowRefs.current[expandedMissionId]?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, 100);
      setExpandedMissionId(null);
      setTimeout(() => setHighlightId(null), 2000);
    }
  }, [expandedMissionId, setExpandedMissionId]);

  const handleRobotClick = (e: React.MouseEvent, robotId: string) => {
    e.stopPropagation();
    selectRobot(robotId);
    navigate('/fleet-map');
  };

  const handleManualControl = (e: React.MouseEvent, robotId: string) => {
    e.stopPropagation();
    navigate('/manual-control', { state: { robotId } });
  };

  return (
    <div>
      <PageHeader title="Mission Management" subtitle="Track and manage active missions" />

      <div className="bg-card rounded-3xl p-6 shadow-sm border border-border">
        <TooltipProvider>
          <table className="w-full">
            <thead>
              <tr className="text-left text-muted-foreground text-xs uppercase tracking-wider">
                <th className="pb-4 font-semibold">Robot</th>
                <th className="pb-4 font-semibold">Session</th>
                <th className="pb-4 font-semibold">Type</th>
                <th className="pb-4 font-semibold">Mode</th>
                <th className="pb-4 font-semibold">Status</th>
                <th className="pb-4 font-semibold">Target</th>
                <th className="pb-4 font-semibold">ETA</th>
                <th className="pb-4 font-semibold">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {missions.map(mission => (
                <>
                  <tr
                    key={mission.id}
                    ref={el => { rowRefs.current[mission.id] = el; }}
                    className={`group hover:bg-secondary/50 transition-all cursor-pointer ${highlightId === mission.id ? 'ring-2 ring-primary' : ''}`}
                    onClick={() => setExpanded(expanded === mission.id ? null : mission.id)}
                  >
                    <td className="py-4">
                      <div className="flex items-center gap-2">
                        <MI icon="smart_toy" className="text-muted-foreground text-sm" />
                        <span
                          onClick={(e) => handleRobotClick(e, mission.robotId)}
                          className="font-bold text-sm text-foreground hover:text-primary hover:underline cursor-pointer transition-colors"
                        >
                          {mission.robotId}
                        </span>
                      </div>
                    </td>
                    <td className="py-4 text-sm text-muted-foreground">{mission.sessionId}</td>
                    <td className="py-4">
                      <span className="text-xs font-bold bg-secondary px-2 py-0.5 rounded-full text-foreground">{mission.type}</span>
                    </td>
                    <td className="py-4">
                      <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${modeBadge[mission.mode]}`}>{mission.mode}</span>
                    </td>
                    <td className="py-4">
                      <span className={`text-xs font-bold px-3 py-1 rounded-full ${statusBadge[mission.status]}`}>{mission.status}</span>
                    </td>
                    <td className="py-4 text-sm text-foreground">{mission.currentTarget}</td>
                    <td className="py-4 text-sm text-muted-foreground">{mission.eta > 0 ? `${mission.eta}s` : '—'}</td>
                    <td className="py-4">
                      <div className="flex items-center gap-1">
                        {mission.status === 'RUNNING' ? (
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <button
                                onClick={e => { e.stopPropagation(); stopMission(mission.id); }}
                                className="p-1.5 rounded-lg hover:bg-secondary text-amber-500 transition-colors"
                              >
                                <MI icon="pause_circle" className="text-lg" />
                              </button>
                            </TooltipTrigger>
                            <TooltipContent>Pause</TooltipContent>
                          </Tooltip>
                        ) : mission.status === 'PAUSED' ? (
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <button
                                onClick={e => { e.stopPropagation(); restartMission(mission.id); }}
                                className="p-1.5 rounded-lg hover:bg-secondary text-emerald-500 transition-colors"
                              >
                                <MI icon="play_circle" className="text-lg" />
                              </button>
                            </TooltipTrigger>
                            <TooltipContent>Resume</TooltipContent>
                          </Tooltip>
                        ) : null}
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <button
                              onClick={(e) => handleManualControl(e, mission.robotId)}
                              className="p-1.5 rounded-lg hover:bg-secondary text-muted-foreground transition-colors"
                            >
                              <MI icon="sports_esports" className="text-lg" />
                            </button>
                          </TooltipTrigger>
                          <TooltipContent>Manual Control Panel</TooltipContent>
                        </Tooltip>
                      </div>
                    </td>
                  </tr>
                  {/* Guide queue expansion */}
                  {expanded === mission.id && mission.guideQueue && (
                    <tr key={`${mission.id}-q`}>
                      <td colSpan={8} className="pb-4 pt-0">
                        <div className="bg-secondary/50 rounded-2xl p-4 ml-8">
                          <p className="text-xs font-bold text-foreground mb-3 uppercase tracking-wider">Guide Queue</p>
                          <div className="flex items-center gap-3">
                            {mission.guideQueue.map((item, i) => (
                              <div key={i} className="flex items-center gap-2">
                                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold border-2 ${
                                  item.status === 'DONE' ? 'bg-emerald-500 text-primary-foreground border-emerald-600' :
                                  item.status === 'ARRIVED' ? 'bg-primary text-primary-foreground border-primary' :
                                  'bg-card text-muted-foreground border-border'
                                }`}>
                                  {item.status === 'DONE' ? <MI icon="check" className="text-sm" /> : i + 1}
                                </div>
                                <div>
                                  <p className="text-sm font-medium text-foreground">{item.poiName}</p>
                                  <p className="text-xs text-muted-foreground">{item.status}</p>
                                </div>
                                {i < mission.guideQueue!.length - 1 && (
                                  <div className="w-8 h-0.5 bg-border" />
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </TooltipProvider>
      </div>
    </div>
  );
}

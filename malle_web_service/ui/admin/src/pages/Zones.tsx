import { useState, useRef, useCallback, useEffect } from 'react';
import { useDashboard } from '@/context/DashboardContext';
import type { Zone, ZoneRules } from '@/context/DashboardContext';
import { MI } from '@/components/MaterialIcon';
import PageHeader from '@/components/PageHeader';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useToast } from '@/hooks/use-toast';

const zoneColors: Record<string, { fill: string; stroke: string; label: string }> = {
  RESTRICTED: { fill: 'rgba(239,68,68,0.15)', stroke: '#ef4444', label: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' },
  MAINTENANCE: { fill: 'rgba(168,85,247,0.15)', stroke: '#a855f7', label: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400' },
  CONGESTED: { fill: 'rgba(234,179,8,0.15)', stroke: '#eab308', label: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400' },
  CAUTION: { fill: 'rgba(249,115,22,0.15)', stroke: '#f97316', label: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400' },
};

type ZoneType = 'RESTRICTED' | 'MAINTENANCE' | 'CAUTION' | 'CONGESTED';

export default function ZonesPage() {
  const { zones, toggleZone, addZone, deleteZone } = useDashboard();
  const { toast } = useToast();
  const svgRef = useRef<SVGSVGElement>(null);

  // Drawing state
  const [drawing, setDrawing] = useState(false);
  const [vertices, setVertices] = useState<{ x: number; y: number }[]>([]);
  const [mousePos, setMousePos] = useState<{ x: number; y: number } | null>(null);

  // Modal state
  const [showModal, setShowModal] = useState(false);
  const [zoneName, setZoneName] = useState('');
  const [zoneType, setZoneType] = useState<ZoneType>('RESTRICTED');
  const [zoneActive, setZoneActive] = useState(true);
  const [priority, setPriority] = useState<'LOW' | 'MEDIUM' | 'HIGH'>('MEDIUM');
  const [maxSpeed, setMaxSpeed] = useState(0.3);
  const [oneWay, setOneWay] = useState(false);
  const [enhancedAvoidance, setEnhancedAvoidance] = useState(true);

  // Delete confirm
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  const getSvgPoint = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
    const svg = svgRef.current;
    if (!svg) return null;
    const pt = svg.createSVGPoint();
    pt.x = e.clientX;
    pt.y = e.clientY;
    const ctm = svg.getScreenCTM();
    if (!ctm) return null;
    const svgPt = pt.matrixTransform(ctm.inverse());
    return { x: Math.round(svgPt.x), y: Math.round(svgPt.y) };
  }, []);

  const handleSvgClick = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
    if (!drawing) return;
    const pt = getSvgPoint(e);
    if (!pt) return;

    // Check if clicking near first vertex to close
    if (vertices.length >= 3) {
      const first = vertices[0];
      const dist = Math.sqrt((pt.x - first.x) ** 2 + (pt.y - first.y) ** 2);
      if (dist < 15) {
        setDrawing(false);
        setMousePos(null);
        setShowModal(true);
        return;
      }
    }

    setVertices(prev => [...prev, pt]);
  }, [drawing, vertices, getSvgPoint]);

  const handleSvgDblClick = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
    if (!drawing || vertices.length < 3) return;
    e.preventDefault();
    setDrawing(false);
    setMousePos(null);
    setShowModal(true);
  }, [drawing, vertices]);

  const handleSvgMouseMove = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
    if (!drawing) return;
    const pt = getSvgPoint(e);
    if (pt) setMousePos(pt);
  }, [drawing, getSvgPoint]);

  // Escape to cancel drawing
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && drawing) {
        setDrawing(false);
        setVertices([]);
        setMousePos(null);
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [drawing]);

  const startDrawing = () => {
    setDrawing(true);
    setVertices([]);
    setMousePos(null);
  };

  const cancelDrawing = () => {
    setDrawing(false);
    setVertices([]);
    setMousePos(null);
  };

  const resetModal = () => {
    setZoneName('');
    setZoneType('RESTRICTED');
    setZoneActive(true);
    setPriority('MEDIUM');
    setMaxSpeed(0.3);
    setOneWay(false);
    setEnhancedAvoidance(true);
  };

  const handleSaveZone = () => {
    if (!zoneName.trim()) return;

    const rules: ZoneRules = { priority };
    if (zoneType === 'CAUTION') {
      rules.maxSpeed = maxSpeed;
      rules.oneWay = oneWay;
    } else if (zoneType === 'CONGESTED') {
      rules.maxSpeed = maxSpeed;
      rules.enhancedObstacleAvoidance = enhancedAvoidance;
    }

    const newZone: Zone = {
      id: `Z-${Date.now().toString(36).toUpperCase()}`,
      name: zoneName.trim(),
      type: zoneType,
      polygon: vertices,
      active: zoneActive,
      rules,
    };

    addZone(newZone);

    // TODO: Connect to backend — syncs with DB and ROS2 costmap
    try {
      fetch('/api/zones', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newZone),
      }).catch(() => {});
    } catch {}

    toast({ title: 'Zone Created', description: `"${newZone.name}" has been added successfully.` });
    setShowModal(false);
    setVertices([]);
    resetModal();
  };

  const handleDeleteZone = (zoneId: string) => {
    deleteZone(zoneId);
    // TODO: Connect to backend — syncs with DB and ROS2 costmap
    try { fetch(`/api/zones/${zoneId}`, { method: 'DELETE' }).catch(() => {}); } catch {}
    toast({ title: 'Zone Deleted', description: 'Zone has been removed.' });
    setDeleteConfirm(null);
  };

  const handleToggleZone = (zoneId: string) => {
    toggleZone(zoneId);
    // TODO: Connect to backend — syncs with DB and ROS2 costmap
    try { fetch(`/api/zones/${zoneId}/toggle`, { method: 'PATCH' }).catch(() => {}); } catch {}
  };

  const getRulesDisplay = (zone: Zone) => {
    switch (zone.type) {
      case 'RESTRICTED': return '🚫 No entry';
      case 'MAINTENANCE': return '🔧 Under maintenance — no entry';
      case 'CAUTION': return `⚠️ Speed limit: ${zone.rules?.maxSpeed ?? 0.3} m/s`;
      case 'CONGESTED': return `🚶 Speed limit: ${zone.rules?.maxSpeed ?? 0.2} m/s • Enhanced avoidance: ${zone.rules?.enhancedObstacleAvoidance !== false ? 'ON' : 'OFF'}`;
      default: return '';
    }
  };

  return (
    <div>
      <PageHeader title="Zone Management" subtitle="Configure restricted and special areas" />

      <div className="flex gap-6 h-[calc(100vh-14rem)]">
        {/* Map */}
        <div className="flex-1 bg-secondary/30 rounded-3xl overflow-hidden relative">
          {/* Drawing instruction banner */}
          {drawing && (
            <div className="absolute top-4 left-1/2 -translate-x-1/2 z-10 bg-primary text-primary-foreground px-4 py-2 rounded-xl text-sm font-semibold shadow-lg flex items-center gap-2">
              <MI icon="draw" className="text-base" />
              Click to place vertices. Click first point or double-click to close polygon.
            </div>
          )}

          <svg
            ref={svgRef}
            className={`w-full h-full ${drawing ? 'cursor-crosshair' : ''}`}
            viewBox="0 0 450 380"
            preserveAspectRatio="xMidYMid meet"
            onClick={handleSvgClick}
            onDoubleClick={handleSvgDblClick}
            onMouseMove={handleSvgMouseMove}
          >
            <defs>
              <pattern id="zoneGrid" x="0" y="0" width="20" height="20" patternUnits="userSpaceOnUse">
                <circle cx="1" cy="1" r="1" className="fill-muted-foreground/20" />
              </pattern>
            </defs>
            <rect width="450" height="380" fill="url(#zoneGrid)" />

            {/* Existing zones */}
            {zones.map(zone => {
              const pts = zone.polygon.map(p => `${p.x},${p.y}`).join(' ');
              const color = zoneColors[zone.type] || zoneColors.CAUTION;
              return (
                <g key={zone.id}>
                  <polygon
                    points={pts}
                    fill={zone.active ? color.fill : 'none'}
                    stroke={color.stroke}
                    strokeWidth="2"
                    strokeDasharray={zone.active ? '' : '6 4'}
                    opacity={zone.active ? 1 : 0.3}
                  />
                  <text x={zone.polygon[0].x + 5} y={zone.polygon[0].y + 20} className="fill-foreground text-[10px] font-bold">{zone.name}</text>
                  <text x={zone.polygon[0].x + 5} y={zone.polygon[0].y + 32} className="fill-muted-foreground text-[8px]">{zone.type}</text>
                </g>
              );
            })}

            {/* Drawing preview */}
            {drawing && vertices.length > 0 && (
              <g>
                {/* Lines between vertices */}
                {vertices.map((v, i) => {
                  if (i === 0) return null;
                  const prev = vertices[i - 1];
                  return <line key={i} x1={prev.x} y1={prev.y} x2={v.x} y2={v.y} stroke="hsl(239,84%,67%)" strokeWidth="2" />;
                })}

                {/* Dashed preview line to mouse */}
                {mousePos && vertices.length > 0 && (
                  <line
                    x1={vertices[vertices.length - 1].x}
                    y1={vertices[vertices.length - 1].y}
                    x2={mousePos.x}
                    y2={mousePos.y}
                    stroke="hsl(239,84%,67%)"
                    strokeWidth="1.5"
                    strokeDasharray="6 4"
                    opacity={0.6}
                  />
                )}

                {/* Vertex dots */}
                {vertices.map((v, i) => (
                  <circle
                    key={i}
                    cx={v.x}
                    cy={v.y}
                    r={i === 0 && vertices.length >= 3 ? 6 : 4}
                    fill={i === 0 && vertices.length >= 3 ? 'hsl(239,84%,67%)' : 'hsl(239,84%,67%)'}
                    stroke="white"
                    strokeWidth="2"
                    className={i === 0 && vertices.length >= 3 ? 'cursor-pointer' : ''}
                  />
                ))}
              </g>
            )}
          </svg>
        </div>

        {/* Zone List */}
        <div className="w-96 space-y-4 overflow-y-auto">
          {drawing ? (
            <button
              onClick={cancelDrawing}
              className="w-full py-3 bg-critical-red text-primary-foreground rounded-xl font-bold flex items-center justify-center gap-2 hover:bg-critical-red/90 active:scale-95 transition-all"
            >
              <MI icon="close" /> Cancel Drawing
            </button>
          ) : (
            <button
              onClick={startDrawing}
              className="w-full py-3 bg-primary text-primary-foreground rounded-xl font-bold flex items-center justify-center gap-2 hover:bg-primary/90 active:scale-95 transition-all"
            >
              <MI icon="add" /> Add Zone
            </button>
          )}

          {zones.map(zone => {
            const color = zoneColors[zone.type] || zoneColors.CAUTION;
            return (
              <div key={zone.id} className="bg-card rounded-2xl p-5 border border-border shadow-sm">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <div className="w-4 h-4 rounded" style={{ backgroundColor: color.stroke }} />
                    <div>
                      <h4 className="font-bold text-foreground">{zone.name}</h4>
                      <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${color.label}`}>{zone.type}</span>
                    </div>
                  </div>
                  <button
                    onClick={() => handleToggleZone(zone.id)}
                    className={`w-12 h-6 rounded-full p-0.5 transition-colors ${zone.active ? 'bg-emerald-500' : 'bg-secondary'}`}
                  >
                    <div className={`w-5 h-5 bg-primary-foreground rounded-full shadow transition-transform ${zone.active ? 'translate-x-6' : 'translate-x-0'}`} />
                  </button>
                </div>
                <p className="text-xs text-muted-foreground mb-1">{zone.polygon.length} vertices • {zone.active ? 'Active' : 'Inactive'}</p>
                <p className="text-xs text-muted-foreground mb-3">{getRulesDisplay(zone)}</p>
                <div className="flex gap-2">
                  <button className="text-xs text-primary font-semibold hover:underline flex items-center gap-1">
                    <MI icon="edit" className="text-sm" /> Edit
                  </button>
                  <button
                    onClick={() => setDeleteConfirm(zone.id)}
                    className="text-xs text-critical-red font-semibold hover:underline flex items-center gap-1"
                  >
                    <MI icon="delete" className="text-sm" /> Delete
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Zone Configuration Modal */}
      <Dialog open={showModal} onOpenChange={(open) => {
        if (!open) {
          setShowModal(false);
          setVertices([]);
          resetModal();
        }
      }}>
        <DialogContent className="bg-card rounded-2xl border border-border shadow-xl max-w-md">
          <DialogHeader>
            <DialogTitle className="text-lg font-bold text-foreground">Configure New Zone</DialogTitle>
          </DialogHeader>

          <div className="space-y-4">
            {/* Zone Name */}
            <div>
              <label className="text-sm font-semibold text-foreground mb-1 block">Zone Name</label>
              <Input
                value={zoneName}
                onChange={e => setZoneName(e.target.value)}
                placeholder="e.g. West Wing Corridor"
                className="rounded-xl"
              />
            </div>

            {/* Zone Type */}
            <div>
              <label className="text-sm font-semibold text-foreground mb-1 block">Zone Type</label>
              <Select value={zoneType} onValueChange={v => setZoneType(v as ZoneType)}>
                <SelectTrigger className="rounded-xl">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="RESTRICTED">🚫 Restricted (No Entry)</SelectItem>
                  <SelectItem value="MAINTENANCE">🔧 Maintenance Zone</SelectItem>
                  <SelectItem value="CONGESTED">🚶 Congested Area</SelectItem>
                  <SelectItem value="CAUTION">⚠️ Caution</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Driving Rules */}
            <div className="bg-secondary/50 rounded-xl p-4">
              <p className="text-xs font-bold text-muted-foreground uppercase tracking-wider mb-2">Driving Rules</p>
              {zoneType === 'RESTRICTED' && (
                <p className="text-sm text-foreground">Robots will be completely blocked from entering this zone.</p>
              )}
              {zoneType === 'MAINTENANCE' && (
                <p className="text-sm text-foreground">Robots cannot enter — area under maintenance.</p>
              )}
              {zoneType === 'CAUTION' && (
                <div className="space-y-3">
                  <div>
                    <label className="text-xs text-muted-foreground">Speed Limit (m/s)</label>
                    <Input type="number" step="0.1" min="0.1" max="2" value={maxSpeed} onChange={e => setMaxSpeed(parseFloat(e.target.value) || 0.3)} className="rounded-xl mt-1" />
                  </div>
                  <label className="flex items-center gap-2 text-sm text-foreground cursor-pointer">
                    <input type="checkbox" checked={oneWay} onChange={e => setOneWay(e.target.checked)} className="rounded" />
                    One-way direction
                  </label>
                </div>
              )}
              {zoneType === 'CONGESTED' && (
                <div className="space-y-3">
                  <div>
                    <label className="text-xs text-muted-foreground">Speed Limit (m/s)</label>
                    <Input type="number" step="0.1" min="0.1" max="2" value={maxSpeed} onChange={e => setMaxSpeed(parseFloat(e.target.value) || 0.2)} className="rounded-xl mt-1" />
                  </div>
                  <label className="flex items-center gap-2 text-sm text-foreground cursor-pointer">
                    <input type="checkbox" checked={enhancedAvoidance} onChange={e => setEnhancedAvoidance(e.target.checked)} className="rounded" />
                    Use enhanced obstacle avoidance
                  </label>
                </div>
              )}
            </div>

            {/* Active toggle */}
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-foreground">Active</span>
              <button
                onClick={() => setZoneActive(!zoneActive)}
                className={`w-12 h-6 rounded-full p-0.5 transition-colors ${zoneActive ? 'bg-emerald-500' : 'bg-secondary'}`}
              >
                <div className={`w-5 h-5 bg-primary-foreground rounded-full shadow transition-transform ${zoneActive ? 'translate-x-6' : 'translate-x-0'}`} />
              </button>
            </div>

            {/* Priority */}
            <div>
              <label className="text-sm font-semibold text-foreground mb-1 block">Priority</label>
              <Select value={priority} onValueChange={v => setPriority(v as 'LOW' | 'MEDIUM' | 'HIGH')}>
                <SelectTrigger className="rounded-xl">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="LOW">Low</SelectItem>
                  <SelectItem value="MEDIUM">Medium</SelectItem>
                  <SelectItem value="HIGH">High</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <DialogFooter className="gap-2 mt-2">
            <button
              onClick={() => { setShowModal(false); setVertices([]); resetModal(); }}
              className="px-4 py-2 bg-secondary text-foreground rounded-xl font-semibold hover:bg-secondary/80 transition-all"
            >
              Cancel
            </button>
            <button
              onClick={handleSaveZone}
              disabled={!zoneName.trim()}
              className="px-4 py-2 bg-primary text-primary-foreground rounded-xl font-bold hover:bg-primary/90 transition-all disabled:opacity-50"
            >
              Save Zone
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      {deleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="bg-card rounded-2xl p-6 shadow-xl border border-border max-w-md w-full mx-4">
            <div className="flex justify-center mb-4">
              <div className="w-12 h-12 rounded-full bg-critical-red/10 flex items-center justify-center">
                <MI icon="warning" className="text-critical-red text-2xl" />
              </div>
            </div>
            <p className="text-center text-foreground font-semibold mb-1">Delete Zone</p>
            <p className="text-center text-sm text-muted-foreground mb-6">
              Are you sure you want to delete "{zones.find(z => z.id === deleteConfirm)?.name}"? This action cannot be undone.
            </p>
            <div className="flex gap-3">
              <button onClick={() => setDeleteConfirm(null)} className="flex-1 py-2.5 bg-secondary text-foreground rounded-xl font-semibold hover:bg-secondary/80 transition-all">
                Cancel
              </button>
              <button onClick={() => handleDeleteZone(deleteConfirm)} className="flex-1 py-2.5 bg-critical-red text-primary-foreground rounded-xl font-bold hover:bg-critical-red/90 active:scale-95 transition-all">
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

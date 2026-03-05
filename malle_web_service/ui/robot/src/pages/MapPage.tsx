import { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useRobotStore } from '@/stores/robotStore';
import { toast } from 'sonner';
import { poiApi } from '@/api/services';

// ── 맵 물리 크기 (미터) ──────────────────────────────────────────────────────
const MAP_WIDTH_M  = 2.45;
const MAP_HEIGHT_M = 2.0;

/**
 * 미터 좌표 → 맵 컨테이너 내 % 위치 변환
 * ROS2 좌표계: x = 오른쪽, y = 위쪽
 * CSS: left = x/width, top = (height-y)/height  (y축 반전)
 */
function toMapPercent(x_m: number, y_m: number) {
  const left = (x_m / MAP_WIDTH_M)                   * 100;
  const top  = ((MAP_HEIGHT_M - y_m) / MAP_HEIGHT_M) * 100;
  return {
    left: `${Math.min(Math.max(left, 2), 98)}%`,
    top:  `${Math.min(Math.max(top,  2), 98)}%`,
  };
}

// POI 타입 → 아이콘
function poiIcon(type: string) {
  const t = (type || '').toLowerCase();
  if (t.includes('cafe') || t.includes('dining') || t.includes('food')) return 'local_cafe';
  if (t.includes('fashion') || t.includes('cloth'))                      return 'checkroom';
  if (t.includes('sport'))                                                return 'sports_soccer';
  if (t.includes('electronic'))                                           return 'devices';
  if (t.includes('station') || t.includes('charger'))                    return 'bolt';
  if (t.includes('lounge'))                                               return 'weekend';
  return 'storefront';
}

// ── POI 타입 정의 ────────────────────────────────────────────────────────────
interface Poi {
  id: number;
  name: string;
  type: string;
  x_m: number;
  y_m: number;
  wait_x_m?: number | null;
  wait_y_m?: number | null;
}

export function MapPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [highlightedPoi, setHighlightedPoi] = useState<number | null>(null);
  const [hoveredPoi, setHoveredPoi]         = useState<number | null>(null);
  const [hoverTimeout, setHoverTimeout]     = useState<ReturnType<typeof setTimeout> | null>(null);
  const [pois, setPois]                     = useState<Poi[]>([]);

  const { robot, addToGuideQueue, lockboxSlots, setPendingPickupStore } = useRobotStore();
  const navigate = useNavigate();

  const hasEmptySlot = lockboxSlots.some(s => s.status === 'EMPTY');

  // ── API에서 POI 로드 ──────────────────────────────────────────────────────
  useEffect(() => {
    poiApi.list()
      .then((data) => setPois(data))
      .catch(() => {});
  }, []);

  // ── highlight 쿼리 파라미터 처리 ─────────────────────────────────────────
  useEffect(() => {
    const highlight = searchParams.get('highlight');
    if (highlight) {
      setHighlightedPoi(Number(highlight));
      searchParams.delete('highlight');
      setSearchParams(searchParams, { replace: true });
      const t = setTimeout(() => setHighlightedPoi(null), 3000);
      return () => clearTimeout(t);
    }
  }, []);

  const handleAddToGuide = (poi: Poi) => {
    addToGuideQueue({
      poiId:         poi.id,
      poiName:       poi.name,
      floor:         `(${poi.x_m.toFixed(2)}m, ${poi.y_m.toFixed(2)}m)`,
      estimatedTime: 2,
    });
    toast.success(`Added ${poi.name} to Guide Queue`, { duration: 2000 });
    setHoveredPoi(null);
  };

  const handleOrderPickup = (poi: Poi) => {
    setPendingPickupStore(poi.id);
    navigate('/mode/pickup');
  };

  // ── robot 위치 (robotStore에서 x_m/y_m 또는 x/y 형태로 올 수 있음) ──────
  const robotX = (robot as any)?.x_m ?? (robot as any)?.location?.x ?? null;
  const robotY = (robot as any)?.y_m ?? (robot as any)?.location?.y ?? null;
  const robotName = (robot as any)?.name ?? 'Robot';

  return (
    <div className="h-full flex flex-col">
      {/* ── 헤더 ── */}
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-page-title">Mall Map</h1>
        <div className="flex items-center space-x-2">
          <button className="p-2 rounded-xl bg-card border border-slate-200 dark:border-slate-700">
            <span className="material-icons-round">add</span>
          </button>
          <button className="p-2 rounded-xl bg-card border border-slate-200 dark:border-slate-700">
            <span className="material-icons-round">remove</span>
          </button>
          <button className="p-2 rounded-xl bg-primary text-white">
            <span className="material-icons-round">my_location</span>
          </button>
        </div>
      </div>

      {/* ── 맵 컨테이너 ── */}
      <div className="flex-1 relative flex items-center justify-center overflow-hidden">
        <div
          className="relative rounded-2xl overflow-hidden border-2 border-slate-200 dark:border-slate-700 shadow-xl"
          style={{
            aspectRatio: '2.45 / 2',
            width: '100%',
            maxWidth: '520px',
          }}
        >
          {/* PGM → PNG 맵 이미지 */}
          <img
            src="/map_end_end.png"
            alt="Mall Map"
            className="absolute inset-0 w-full h-full"
            style={{ imageRendering: 'pixelated', objectFit: 'fill' }}
            draggable={false}
          />
          {/* 반투명 오버레이 */}
          <div className="absolute inset-0 bg-slate-100/30 dark:bg-slate-900/30" />

          {/* ── 로봇 마커 ── */}
          {robotX !== null && robotY !== null && (
            <div
              className="absolute transform -translate-x-1/2 -translate-y-1/2 z-30"
              style={toMapPercent(robotX, robotY)}
            >
              <div className="relative">
                <div className="w-10 h-10 rounded-full bg-primary flex items-center justify-center shadow-lg">
                  <span className="material-icons-round text-white">smart_toy</span>
                </div>
                <div className="absolute inset-0 rounded-full bg-primary/30 animate-ping" />
                <div className="absolute -bottom-5 left-1/2 -translate-x-1/2 bg-foreground text-background text-[9px] font-bold px-2 py-0.5 rounded-full whitespace-nowrap">
                  {robotName}
                </div>
              </div>
            </div>
          )}

          {/* ── POI 마커 ── */}
          {pois.map((poi) => {
            const pos          = toMapPercent(poi.x_m, poi.y_m);
            const isHighlighted = highlightedPoi === poi.id;
            const isHovered     = hoveredPoi     === poi.id;

            return (
              <div
                key={poi.id}
                className="absolute transform -translate-x-1/2 -translate-y-1/2 cursor-pointer z-10"
                style={pos}
                onMouseEnter={() => {
                  if (hoverTimeout) clearTimeout(hoverTimeout);
                  setHoveredPoi(poi.id);
                }}
                onMouseLeave={() => {
                  const t = setTimeout(() => setHoveredPoi(null), 400);
                  setHoverTimeout(t);
                }}
              >
                {/* 마커 원 */}
                <div className={`w-9 h-9 rounded-full flex items-center justify-center shadow-md transition-all duration-300 ${
                  isHighlighted
                    ? 'bg-primary ring-4 ring-primary/40 scale-125'
                    : 'bg-card'
                }`}>
                  <span className={`material-icons-round text-sm ${
                    isHighlighted ? 'text-white' : 'text-primary'
                  }`}>
                    {poiIcon(poi.type)}
                  </span>
                </div>
                {isHighlighted && (
                  <div className="absolute inset-0 w-9 h-9 rounded-full bg-primary/30 animate-ping" />
                )}
                {/* 이름 라벨 */}
                <span className={`absolute -bottom-5 left-1/2 -translate-x-1/2 whitespace-nowrap text-[10px] font-semibold px-2 py-0.5 rounded-lg shadow-sm transition-all duration-300 ${
                  isHighlighted ? 'bg-primary text-white scale-110' : 'bg-card text-foreground'
                }`}>
                  {poi.name}
                </span>

                {/* ── 호버 팝업 ── */}
                {isHovered && (
                  <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-[60]">
                    <div className="bg-card rounded-2xl p-4 shadow-xl border border-slate-200 dark:border-slate-700 w-52">
                      <div className="flex items-center space-x-3 mb-3">
                        <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
                          <span className="material-icons-round text-primary">{poiIcon(poi.type)}</span>
                        </div>
                        <div>
                          <p className="font-semibold text-foreground text-sm">{poi.name}</p>
                          <p className="text-xs text-muted-foreground">{poi.type}</p>
                        </div>
                      </div>
                      <p className="text-xs text-muted-foreground font-mono mb-3">
                        {poi.x_m.toFixed(3)}m, {poi.y_m.toFixed(3)}m
                      </p>
                      <div className="flex space-x-2">
                        <button
                          onClick={() => handleAddToGuide(poi)}
                          className="flex-1 btn-secondary text-xs py-2 flex items-center justify-center gap-1"
                        >
                          <span className="material-icons-round text-sm">alt_route</span>
                          Guide
                        </button>
                        {hasEmptySlot && (
                          <button
                            onClick={() => handleOrderPickup(poi)}
                            className="flex-1 btn-primary text-xs py-2 flex items-center justify-center gap-1"
                          >
                            <span className="material-icons-round text-sm">shopping_bag</span>
                            Pickup
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}

          {/* ── 축척 표시 ── */}
          <div className="absolute bottom-3 left-3 flex items-center gap-1 bg-card/80 backdrop-blur-sm rounded-lg px-2 py-1">
            <div className="h-[2px] w-8 bg-foreground/60" />
            <span className="text-[9px] text-foreground/60 font-medium">0.5m</span>
          </div>
        </div>
      </div>

      {/* ── 범례 ── */}
      <div className="mt-3 bg-card/90 backdrop-blur-sm rounded-2xl p-3 shadow-lg border border-slate-200 dark:border-slate-700">
        <div className="flex items-center gap-4">
          <p className="text-xs font-bold text-muted-foreground uppercase tracking-wide">Legend</p>
          <div className="flex items-center gap-1.5">
            <div className="w-5 h-5 rounded-full bg-primary flex items-center justify-center">
              <span className="material-icons-round text-white text-xs">smart_toy</span>
            </div>
            <span className="text-xs text-foreground">Robot</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-5 h-5 rounded-full bg-card border border-primary flex items-center justify-center">
              <span className="material-icons-round text-primary text-xs">storefront</span>
            </div>
            <span className="text-xs text-foreground">POI</span>
          </div>
          <div className="ml-auto text-xs text-muted-foreground font-mono">2.5m × 2.0m</div>
        </div>
      </div>
    </div>
  );
}
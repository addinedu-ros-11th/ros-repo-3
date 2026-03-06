import { useState, useEffect, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useRobotStore } from '@/stores/robotStore';
import { toast } from 'sonner';
import { poiApi } from '@/api/services';

// ── 맵 물리 크기 (미터) ──────────────────────────────────────────────────────
const MAP_WIDTH_M  = 2.5;
const MAP_HEIGHT_M = 2.0;
const MAP_DB_MIN_X = 0.1;
const MAP_DB_MIN_Y = 0.1;
const MAP_OFFSET   = { left: 3.8462, top: 4.6512, right: 96.0385, bottom: 95.1163 };


const MIN_SCALE = 1;
const MAX_SCALE = 6;

function toMapPercent(x_m: number, y_m: number) {
  const innerW = MAP_OFFSET.right  - MAP_OFFSET.left;
  const innerH = MAP_OFFSET.bottom - MAP_OFFSET.top;
  const ratioX = (x_m - MAP_DB_MIN_X) / (MAP_WIDTH_M  - MAP_DB_MIN_X);
  const ratioY = (y_m - MAP_DB_MIN_Y) / (MAP_HEIGHT_M - MAP_DB_MIN_Y);
  const left = MAP_OFFSET.left + ratioX * innerW;
  const top  = MAP_OFFSET.top  + (1 - ratioY) * innerH;
  return {
    left: `${Math.min(Math.max(left, 0), 100)}%`,
    top:  `${Math.min(Math.max(top,  0), 100)}%`,
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
  map_x_m?: number | null;
  map_y_m?: number | null;
  wait_x_m?: number | null;
  wait_y_m?: number | null;
}

// 호버 상태: POI id + 마커의 화면 좌표
interface HoveredPoi {
  id: number;
  rect: DOMRect;
}

function getTouchDist(a: Touch, b: Touch) {
  return Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY);
}
function getTouchMid(a: Touch, b: Touch) {
  return { x: (a.clientX + b.clientX) / 2, y: (a.clientY + b.clientY) / 2 };
}

export function MapPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [highlightedPoi, setHighlightedPoi] = useState<number | null>(null);
  const [hoveredPoi, setHoveredPoi]         = useState<HoveredPoi | null>(null);
  const [hoverTimeout, setHoverTimeout]     = useState<ReturnType<typeof setTimeout> | null>(null);
  const [pois, setPois]                     = useState<Poi[]>([]);

  const { robot, addToGuideQueue, lockboxSlots, setPendingPickupStore } = useRobotStore();
  const navigate = useNavigate();
  const hasEmptySlot = lockboxSlots.some(s => s.status === 'EMPTY');

  // ── 줌/패닝 상태 ──────────────────────────────────────────────
  const [transform, setTransform] = useState({ x: 0, y: 0, scale: 1 });
  const mapWrapRef = useRef<HTMLDivElement>(null);

  // 드래그
  const isDragging      = useRef(false);
  const lastPointer     = useRef({ x: 0, y: 0 });
  const didMove         = useRef(false); // 탭 vs 드래그 구분

  // 핀치
  const lastPinchDist = useRef<number | null>(null);
  const lastPinchMid  = useRef<{ x: number; y: number } | null>(null);

  // ── 헬퍼 ─────────────────────────────────────────────────────
  const clamp = useCallback((x: number, y: number, scale: number) => ({
    x,
    y,
    scale: Math.min(MAX_SCALE, Math.max(MIN_SCALE, scale)),
  }), []);

  const zoomAt = useCallback((
    prev: { x: number; y: number; scale: number },
    ox: number, oy: number,
    newScale: number
  ) => {
    const s = Math.min(MAX_SCALE, Math.max(MIN_SCALE, newScale));
    const ratio = s / prev.scale;
    return { x: ox - ratio * (ox - prev.x), y: oy - ratio * (oy - prev.y), scale: s };
  }, []);

  // ── 마우스 휠 ────────────────────────────────────────────────
  useEffect(() => {
    const el = mapWrapRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const rect = el.getBoundingClientRect();
      const ox = e.clientX - rect.left;
      const oy = e.clientY - rect.top;
      setTransform(prev => {
        const factor = e.deltaY > 0 ? 0.85 : 1.15;
        return zoomAt(prev, ox, oy, prev.scale * factor);
      });
    };
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, [zoomAt]);

  // ── 터치 (iPad Safari) ───────────────────────────────────────
  useEffect(() => {
    const el = mapWrapRef.current;
    if (!el) return;

    const onTouchStart = (e: TouchEvent) => {
      if (e.touches.length === 2) {
        const [a, b] = [e.touches[0], e.touches[1]];
        lastPinchDist.current = getTouchDist(a, b);
        lastPinchMid.current  = getTouchMid(a, b);
      } else if (e.touches.length === 1) {
        lastPointer.current = { x: e.touches[0].clientX, y: e.touches[0].clientY };
        didMove.current = false;
      }
    };

    const onTouchMove = (e: TouchEvent) => {
      e.preventDefault();
      const rect = el.getBoundingClientRect();

      if (e.touches.length === 2) {
        const [a, b] = [e.touches[0], e.touches[1]];
        const dist = getTouchDist(a, b);
        const mid  = getTouchMid(a, b);

        if (lastPinchDist.current !== null && lastPinchMid.current !== null) {
          const scaleRatio = dist / lastPinchDist.current;
          const ox = mid.x - rect.left;
          const oy = mid.y - rect.top;
          const dx = mid.x - lastPinchMid.current.x;
          const dy = mid.y - lastPinchMid.current.y;

          setTransform(prev => {
            const zoomed = zoomAt(prev, ox, oy, prev.scale * scaleRatio);
            return clamp(zoomed.x + dx, zoomed.y + dy, zoomed.scale);
          });
        }
        lastPinchDist.current = dist;
        lastPinchMid.current  = mid;

      } else if (e.touches.length === 1) {
        const dx = e.touches[0].clientX - lastPointer.current.x;
        const dy = e.touches[0].clientY - lastPointer.current.y;
        lastPointer.current = { x: e.touches[0].clientX, y: e.touches[0].clientY };
        if (Math.abs(dx) > 2 || Math.abs(dy) > 2) didMove.current = true;
        setTransform(prev => clamp(prev.x + dx, prev.y + dy, prev.scale));
      }
    };

    const onTouchEnd = (e: TouchEvent) => {
      if (e.touches.length < 2) {
        lastPinchDist.current = null;
        lastPinchMid.current  = null;
      }
    };

    el.addEventListener('touchstart',  onTouchStart,  { passive: true });
    el.addEventListener('touchmove',   onTouchMove,   { passive: false });
    el.addEventListener('touchend',    onTouchEnd,    { passive: true });
    el.addEventListener('touchcancel', onTouchEnd,    { passive: true });
    return () => {
      el.removeEventListener('touchstart',  onTouchStart);
      el.removeEventListener('touchmove',   onTouchMove);
      el.removeEventListener('touchend',    onTouchEnd);
      el.removeEventListener('touchcancel', onTouchEnd);
    };
  }, [zoomAt, clamp]);

  // ── 마우스 드래그 (데스크톱) ─────────────────────────────────
  const onMouseDown = (e: React.MouseEvent) => {
    if ((e.target as Element).closest('[data-poi]')) return;
    isDragging.current  = true;
    didMove.current     = false;
    lastPointer.current = { x: e.clientX, y: e.clientY };
  };
  const onMouseMove = (e: React.MouseEvent) => {
    if (!isDragging.current) return;
    const dx = e.clientX - lastPointer.current.x;
    const dy = e.clientY - lastPointer.current.y;
    lastPointer.current = { x: e.clientX, y: e.clientY };
    if (Math.abs(dx) > 2 || Math.abs(dy) > 2) didMove.current = true;
    setTransform(prev => clamp(prev.x + dx, prev.y + dy, prev.scale));
  };
  const onMouseUp    = () => { isDragging.current = false; };
  const onMouseLeave = () => { isDragging.current = false; };

  // ── 줌 버튼 ──────────────────────────────────────────────────
  const zoomStep = (factor: number) => {
    const rect = mapWrapRef.current?.getBoundingClientRect();
    if (!rect) return;
    setTransform(prev => zoomAt(prev, rect.width / 2, rect.height / 2, prev.scale * factor));
  };
  const resetView = () => setTransform({ x: 0, y: 0, scale: 1 });

  const centerOnRobot = () => {
    if (robotX === null || robotY === null || !mapWrapRef.current) return;
    const rect  = mapWrapRef.current.getBoundingClientRect();
    const pct   = toMapPercent(robotX, robotY);
    const rx    = parseFloat(pct.left) / 100 * rect.width;
    const ry    = parseFloat(pct.top)  / 100 * rect.height;
    setTransform(prev => clamp(
      rect.width  / 2 - rx * prev.scale,
      rect.height / 2 - ry * prev.scale,
      prev.scale,
    ));
  };

  // ── API / 쿼리 파라미터 ───────────────────────────────────────
  useEffect(() => {
    poiApi.list()
      .then(data => setPois(data))
      .catch(() => {});
  }, []);

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

  // 현재 호버된 POI 데이터
  const hoveredPoiData = hoveredPoi ? pois.find(p => p.id === hoveredPoi.id) : null;

  return (
    <div className="h-full flex flex-col">
      {/* ── 헤더 ── */}
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-page-title">Mall Map</h1>
        <div className="flex items-center space-x-2">
          <button
            onClick={() => zoomStep(1.4)}
            className="p-2 rounded-xl bg-card border border-slate-200 dark:border-slate-700 active:scale-95 transition-transform"
          >
            <span className="material-icons-round">add</span>
          </button>
          <button
            onClick={() => zoomStep(0.7)}
            className="p-2 rounded-xl bg-card border border-slate-200 dark:border-slate-700 active:scale-95 transition-transform"
          >
            <span className="material-icons-round">remove</span>
          </button>
          <button
            onClick={centerOnRobot}
            className="p-2 rounded-xl bg-primary text-white active:scale-95 transition-transform"
            title="로봇 위치로 이동"
          >
            <span className="material-icons-round">my_location</span>
          </button>
          {transform.scale !== 1 && (
            <button
              onClick={resetView}
              className="px-3 py-2 rounded-xl bg-card border border-slate-200 dark:border-slate-700 text-xs font-mono text-muted-foreground active:scale-95 transition-transform"
              title="줌 초기화"
            >
              {Math.round(transform.scale * 100)}%
            </button>
          )}
        </div>
      </div>

      {/* ── 맵 외부 컨테이너 (줌/패닝 이벤트 수신) ── */}
      <div
        ref={mapWrapRef}
        className="flex-1 relative overflow-hidden touch-none select-none"
        style={{ cursor: isDragging.current ? 'grabbing' : 'grab' }}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
        onMouseLeave={onMouseLeave}
      >
        {/* 변환 레이어 */}
        <div
          className="absolute inset-0 flex items-center justify-center overflow-hidden"
          style={{
            transform:       `translate(${transform.x}px, ${transform.y}px) scale(${transform.scale})`,
            transformOrigin: '0 0',
            willChange:      'transform',
          }}
        >
          {/* 맵 카드 */}
          <div
            className="relative rounded-2xl overflow-hidden border-2 border-slate-200 dark:border-slate-700 shadow-xl"
            style={{
              aspectRatio: '2.5 / 2',
              width:       '100%',
              maxWidth:    'min(800px, 90vw, 90vh)',
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
              const pos = toMapPercent(
                poi.map_x_m ?? poi.x_m,
                poi.map_y_m ?? poi.y_m
              );
              const isHighlighted = highlightedPoi === poi.id;
              return (
                <div
                  key={poi.id}
                  data-poi={poi.id}
                  className="absolute transform -translate-x-1/2 -translate-y-1/2 cursor-pointer z-10"
                  style={pos}
                  onMouseEnter={(e) => {
                    if (didMove.current) return; // 드래그 중 호버 무시
                    if (hoverTimeout) clearTimeout(hoverTimeout);
                    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
                    setHoveredPoi({ id: poi.id, rect });
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
                </div>
              );
            })}

            {/* ── 좌표 확인용 임시 마커 ── */}
            {/* {[
              { label: '(0.1,0.1)',    x: 0.1,    y: 0.1 },
              { label: '(2.5,2.0)', x: 2.5, y: 2.0 },
              { label: '(1.25,1.0)', x: 1.25, y: 1.0 },
            ].map(({ label, x, y }) => (
              <div
                key={label}
                className="absolute transform -translate-x-1/2 -translate-y-1/2 z-50"
                style={toMapPercent(x, y)}
              >
                <div className="w-3 h-3 rounded-full bg-red-500 shadow-md" />
                <span className="absolute top-3 left-1/2 -translate-x-1/2 text-[9px] text-red-500 font-bold whitespace-nowrap">
                  {label}
                </span>
              </div>
            ))} */}
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

      {/* ── 호버 팝업 (Portal) ── */}
      {hoveredPoi && hoveredPoiData && createPortal(
        <div
          className="fixed z-[9999] pointer-events-auto"
          style={{
            top:       hoveredPoi.rect.top - 8,
            left:      hoveredPoi.rect.left + hoveredPoi.rect.width / 2,
            transform: 'translate(-50%, -100%)',
          }}
          onMouseEnter={() => {
            if (hoverTimeout) clearTimeout(hoverTimeout);
          }}
          onMouseLeave={() => {
            const t = setTimeout(() => setHoveredPoi(null), 400);
            setHoverTimeout(t);
          }}
        >
          <div className="bg-card rounded-2xl p-4 shadow-xl border border-slate-200 dark:border-slate-700 w-64">
            <div className="flex items-center space-x-3 mb-3">
              <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
                <span className="material-icons-round text-primary">{poiIcon(hoveredPoiData.type)}</span>
              </div>
              <div>
                <p className="font-semibold text-foreground text-sm">{hoveredPoiData.name}</p>
                <p className="text-xs text-muted-foreground">{hoveredPoiData.type}</p>
              </div>
            </div>
            <p className="text-xs text-muted-foreground font-mono mb-3">
              {hoveredPoiData.x_m.toFixed(3)}m, {hoveredPoiData.y_m.toFixed(3)}m
            </p>
            <div className="flex space-x-2">
              <button
                onClick={() => handleAddToGuide(hoveredPoiData)}
                className="flex-1 btn-secondary text-xs py-2 flex items-center justify-center gap-1"
              >
                <span className="material-icons-round text-sm">alt_route</span>
                Guide
              </button>
              {hasEmptySlot && (
                <button
                  onClick={() => handleOrderPickup(hoveredPoiData)}
                  className="flex-1 btn-primary text-xs py-2 flex items-center justify-center gap-1"
                >
                  <span className="material-icons-round text-sm">shopping_bag</span>
                  Pickup
                </button>
              )}
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}
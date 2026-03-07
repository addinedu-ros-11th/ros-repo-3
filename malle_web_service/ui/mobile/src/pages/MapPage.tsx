import { useState, useRef, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppStore } from '@/store/appStore';
import { BottomNav } from '@/components/layout/BottomNav';
import { VoiceCommandPanel } from '@/components/voice/VoiceCommandPanel';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

// 맵 물리 크기 (미터)
const MAP_WIDTH_M  = 2.5;
const MAP_HEIGHT_M = 2.0;
const MAP_DB_MIN_X = 0.1;   // DB 좌표 최솟값
const MAP_DB_MIN_Y = 0.1;
const MAP_OFFSET = { left: 3.8462, top: 4.6512, right: 96.0385, bottom: 95.1163 };

const MIN_SCALE = 1;
const MAX_SCALE = 6;

function toMapPercent(x_m: number, y_m: number) {
  const innerW = MAP_OFFSET.right  - MAP_OFFSET.left;
  const innerH = MAP_OFFSET.bottom - MAP_OFFSET.top;
  // DB 좌표를 흰색 영역 내 비율로 변환 (0.1~2.5 → 0~1)
  const ratioX = (x_m - MAP_DB_MIN_X) / (MAP_WIDTH_M  - MAP_DB_MIN_X);
  const ratioY = (y_m - MAP_DB_MIN_Y) / (MAP_HEIGHT_M - MAP_DB_MIN_Y);
  const left = MAP_OFFSET.left + ratioX * innerW;
  const top  = MAP_OFFSET.top  + (1 - ratioY) * innerH;  // y축 반전
  return {
    left: `${Math.min(Math.max(left, 0), 100)}%`,
    top:  `${Math.min(Math.max(top,  0), 100)}%`,
  };
}

/** 두 터치 포인트 사이의 거리 */
function getTouchDist(a: React.Touch, b: React.Touch) {
  return Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY);
}

/** 두 터치 포인트의 중심점 */
function getTouchMid(a: React.Touch, b: React.Touch) {
  return { x: (a.clientX + b.clientX) / 2, y: (a.clientY + b.clientY) / 2 };
}

export default function MapPage() {
  const navigate = useNavigate();
  const { robot, pois, addToGuideQueue, sessionState, session, taskMission } = useAppStore();
  const [selectedPoi, setSelectedPoi] = useState<string | null>(null);
  const [isVoiceOpen, setIsVoiceOpen] = useState(false);

  const isActive   = sessionState === 'ACTIVE';
  const isTaskMode = isActive && session.type === 'TASK' && !!taskMission;
  const selectedPoiData = pois.find(p => p.id === selectedPoi);

  // ── 줌/패닝 상태 ──────────────────────────────────────────────
  const [transform, setTransform] = useState({ x: 0, y: 0, scale: 1 });
  const mapWrapRef = useRef<HTMLDivElement>(null);

  // 드래그 패닝
  const isDragging = useRef(false);
  const lastPointer = useRef({ x: 0, y: 0 });
  const didDrag = useRef(false); // 드래그 vs 탭 구분

  // 핀치 줌
  const lastPinchDist = useRef<number | null>(null);
  const lastPinchMid  = useRef<{ x: number; y: number } | null>(null);

  const clamp = useCallback((x: number, y: number, scale: number) => {
    const s = Math.min(MAX_SCALE, Math.max(MIN_SCALE, scale));
    return { x, y, scale: s };
  }, []);

  /** scale + origin 기준 새 translate 계산 */
  const zoomAt = useCallback((
    prev: { x: number; y: number; scale: number },
    originX: number, originY: number,
    newScale: number
  ) => {
    const ratio = newScale / prev.scale;
    return clamp(
      originX - ratio * (originX - prev.x),
      originY - ratio * (originY - prev.y),
      newScale
    );
  }, [clamp]);

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
        const delta = e.deltaY > 0 ? 0.85 : 1.15;
        return zoomAt(prev, ox, oy, Math.min(MAX_SCALE, Math.max(MIN_SCALE, prev.scale * delta)));
      });
    };
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, [zoomAt]);

  // ── 터치 이벤트 ──────────────────────────────────────────────
  const handleTouchStart = (e: React.TouchEvent) => {
    if (e.touches.length === 2) {
      const [a, b] = [e.touches[0], e.touches[1]];
      lastPinchDist.current = getTouchDist(a, b);
      lastPinchMid.current  = getTouchMid(a, b);
    } else if (e.touches.length === 1) {
      lastPointer.current = { x: e.touches[0].clientX, y: e.touches[0].clientY };
      didDrag.current = false;
    }
  };

  const handleTouchMove = (e: React.TouchEvent) => {
    e.preventDefault(); // 브라우저 스크롤/핀치 막기
    if (e.touches.length === 2) {
      const [a, b] = [e.touches[0], e.touches[1]];
      const dist = getTouchDist(a, b);
      const mid  = getTouchMid(a, b);
      const rect = mapWrapRef.current!.getBoundingClientRect();

      if (lastPinchDist.current !== null && lastPinchMid.current !== null) {
        const scaleRatio = dist / lastPinchDist.current;
        const ox = mid.x - rect.left;
        const oy = mid.y - rect.top;

        // 핀치 줌 + 핀치 이동(pan) 동시 처리
        const dx = mid.x - lastPinchMid.current.x;
        const dy = mid.y - lastPinchMid.current.y;

        setTransform(prev => {
          const newScale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, prev.scale * scaleRatio));
          const zoomed   = zoomAt(prev, ox, oy, newScale);
          return clamp(zoomed.x + dx, zoomed.y + dy, zoomed.scale);
        });
      }
      lastPinchDist.current = dist;
      lastPinchMid.current  = mid;
    } else if (e.touches.length === 1) {
      const dx = e.touches[0].clientX - lastPointer.current.x;
      const dy = e.touches[0].clientY - lastPointer.current.y;
      lastPointer.current = { x: e.touches[0].clientX, y: e.touches[0].clientY };
      if (Math.abs(dx) > 2 || Math.abs(dy) > 2) didDrag.current = true;
      setTransform(prev => clamp(prev.x + dx, prev.y + dy, prev.scale));
    }
  };

  const handleTouchEnd = (e: React.TouchEvent) => {
    if (e.touches.length < 2) {
      lastPinchDist.current = null;
      lastPinchMid.current  = null;
    }
  };

  // ── 마우스 드래그 (데스크톱) ─────────────────────────────────
  const handleMouseDown = (e: React.MouseEvent) => {
    if ((e.target as Element).closest('[data-poi]')) return;
    isDragging.current   = true;
    didDrag.current      = false;
    lastPointer.current  = { x: e.clientX, y: e.clientY };
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging.current) return;
    const dx = e.clientX - lastPointer.current.x;
    const dy = e.clientY - lastPointer.current.y;
    lastPointer.current = { x: e.clientX, y: e.clientY };
    if (Math.abs(dx) > 2 || Math.abs(dy) > 2) didDrag.current = true;
    setTransform(prev => clamp(prev.x + dx, prev.y + dy, prev.scale));
  };

  const handleMouseUp   = () => { isDragging.current = false; };
  const handleMouseLeave = () => { isDragging.current = false; };

  // ── 줌 버튼 ──────────────────────────────────────────────────
  const zoomIn  = () => {
    const rect = mapWrapRef.current?.getBoundingClientRect();
    if (!rect) return;
    setTransform(prev => zoomAt(prev, rect.width / 2, rect.height / 2, Math.min(MAX_SCALE, prev.scale * 1.4)));
  };
  const zoomOut = () => {
    const rect = mapWrapRef.current?.getBoundingClientRect();
    if (!rect) return;
    setTransform(prev => zoomAt(prev, rect.width / 2, rect.height / 2, Math.max(MIN_SCALE, prev.scale * 0.7)));
  };
  const resetView = () => setTransform({ x: 0, y: 0, scale: 1 });

  // 로봇 위치로 이동
  const centerOnRobot = () => {
    if (!robot || !mapWrapRef.current) return;
    const rect = mapWrapRef.current.getBoundingClientRect();
    const pct  = toMapPercent(robot.location.x, robot.location.y);
    const rx   = parseFloat(pct.left) / 100 * rect.width;
    const ry   = parseFloat(pct.top)  / 100 * rect.height;
    const cx   = rect.width  / 2;
    const cy   = rect.height / 2;
    setTransform(prev => clamp(cx - rx * prev.scale, cy - ry * prev.scale, prev.scale));
  };

  // ── 헬퍼 ─────────────────────────────────────────────────────
  const handleAddToGuide = () => {
    if (selectedPoiData && !isTaskMode) {
      addToGuideQueue(selectedPoiData);
      setSelectedPoi(null);
    }
  };

  const poiIcon = (category: string) => {
    const c = (category || '').toLowerCase();
    if (c.includes('cafe') || c.includes('dining') || c.includes('food')) return 'local_cafe';
    if (c.includes('fashion') || c.includes('cloth'))                      return 'checkroom';
    if (c.includes('sport'))                                                return 'sports_soccer';
    if (c.includes('electronic'))                                           return 'devices';
    if (c.includes('station') || c.includes('charger'))                    return 'bolt';
    if (c.includes('lounge'))                                               return 'weekend';
    return 'storefront';
  };

  return (
    <TooltipProvider delayDuration={200}>
      <div className="fixed inset-0 z-10 flex flex-col max-w-[430px] mx-auto bg-background">

        {/* ── 맵 영역 ── */}
        <div className="flex-1 relative bg-muted overflow-hidden">

          {/* 줌/패닝 가능한 외부 컨테이너 */}
          <div
            ref={mapWrapRef}
            className="absolute inset-0 overflow-hidden touch-none"
            style={{ cursor: isDragging.current ? 'grabbing' : 'grab' }}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseLeave}
            onTouchStart={handleTouchStart}
            onTouchMove={handleTouchMove}
            onTouchEnd={handleTouchEnd}
          >
            {/* 맵 컨테이너 — 변환 적용 */}
            <div
              className="absolute inset-0 flex items-center justify-center p-4"
              style={{
                transform: `translate(${transform.x}px, ${transform.y}px) scale(${transform.scale})`,
                transformOrigin: '0 0',
                willChange: 'transform',
              }}
            >
              <div
                className="relative rounded-2xl overflow-hidden border-2 border-border/60 shadow-xl"
                style={{
                  aspectRatio: '520 / 430',
                  width: '100%',
                  maxWidth: '380px',
                  maxHeight: 'calc(100vh - 200px)',
                }}
              >
                {/* PGM 맵 이미지 */}
                <img
                  src="/map_end_end.png"
                  alt="Mall Map"
                  className="absolute inset-0 w-full h-full"
                  style={{ imageRendering: 'pixelated', objectFit: 'fill' }}
                  draggable={false}
                />

                {/* 반투명 오버레이 */}
                <div className="absolute inset-0 bg-background/20" />

                {/* ── POI 마커 ── */}
                {pois.map((poi) => {
                  const pos = toMapPercent(poi.map_x ?? poi.x, poi.map_y ?? poi.y);
                  return (
                    <Tooltip key={poi.id}>
                      <TooltipTrigger asChild>
                        <button
                          data-poi={poi.id}
                          onClick={(e) => {
                            e.stopPropagation();
                            if (!didDrag.current) setSelectedPoi(poi.id);
                          }}
                          className={`absolute flex flex-col items-center gap-0.5 transform -translate-x-1/2 -translate-y-1/2 transition-all z-10 ${
                            selectedPoi === poi.id ? 'scale-125 z-20' : 'hover:scale-110'
                          }`}
                          style={pos}
                        >
                          <div className={`w-7 h-7 rounded-full flex items-center justify-center shadow-md border-2 transition-colors ${
                            selectedPoi === poi.id
                              ? 'bg-primary border-primary text-primary-foreground'
                              : 'bg-card border-border text-foreground'
                          }`}>
                            <span className="material-icons-round text-xs">
                              {poiIcon(poi.category)}
                            </span>
                          </div>
                          <span className={`text-[9px] font-semibold px-1.5 py-0.5 rounded-md shadow-sm whitespace-nowrap max-w-[64px] truncate ${
                            selectedPoi === poi.id
                              ? 'bg-primary text-primary-foreground'
                              : 'bg-card/90 text-foreground'
                          }`}>
                            {poi.name}
                          </span>
                        </button>
                      </TooltipTrigger>
                      <TooltipContent side="top" className="text-xs font-semibold">
                        {poi.name} ({poi.x.toFixed(2)}m, {poi.y.toFixed(2)}m)
                      </TooltipContent>
                    </Tooltip>
                  );
                })}

                {/* ── 로봇 마커 ── */}
                {isActive && robot && (
                  <div
                    className="absolute transform -translate-x-1/2 -translate-y-1/2 z-30"
                    style={toMapPercent(robot.location.x, robot.location.y)}
                  >
                    <div className="relative">
                      <div className="w-9 h-9 rounded-full bg-primary flex items-center justify-center shadow-lg">
                        <span className="material-icons-round text-primary-foreground text-lg">smart_toy</span>
                      </div>
                      <div className="absolute inset-0 rounded-full bg-primary/30 animate-ping" />
                      <div className="absolute -bottom-5 left-1/2 -translate-x-1/2 bg-foreground text-background text-[9px] font-bold px-2 py-0.5 rounded-full whitespace-nowrap">
                        {robot.name}
                      </div>
                    </div>
                  </div>
                )}

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

                {/* 좌표 원점 */}
                <div className="absolute bottom-1.5 left-1.5 w-1.5 h-1.5 rounded-full bg-muted-foreground/40" />
              </div>
            </div>
          </div>

          {/* ── 줌 컨트롤 (UI — 변환 영향 없음) ── */}
          <div className="absolute top-4 right-4 flex flex-col gap-2 z-20 pointer-events-auto">
            <button
              onClick={zoomIn}
              className="w-10 h-10 rounded-full bg-card shadow-md flex items-center justify-center active-press-sm"
            >
              <span className="material-icons-round text-foreground">add</span>
            </button>
            <button
              onClick={zoomOut}
              className="w-10 h-10 rounded-full bg-card shadow-md flex items-center justify-center active-press-sm"
            >
              <span className="material-icons-round text-foreground">remove</span>
            </button>
            <button
              onClick={centerOnRobot}
              className="w-10 h-10 rounded-full bg-card shadow-md flex items-center justify-center active-press-sm mt-2"
            >
              <span className="material-icons-round text-primary">my_location</span>
            </button>
          </div>

          {/* 줌 배율 표시 */}
          {transform.scale !== 1 && (
            <div className="absolute bottom-3 right-4 z-20 pointer-events-none">
              <button
                onClick={resetView}
                className="pointer-events-auto text-[10px] text-muted-foreground bg-card/90 px-2 py-1 rounded-md border border-border shadow-sm active-press-sm"
              >
                {Math.round(transform.scale * 100)}% · 초기화
              </button>
            </div>
          )}

          {/* ── 범례 ── */}
          <div className="absolute top-4 left-4 bg-card/90 backdrop-blur-sm rounded-xl p-3 shadow-md z-20 pointer-events-none">
            <p className="text-xs font-bold text-muted-foreground mb-2">Legend</p>
            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-primary" />
                <span className="text-xs text-foreground">Robot</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="material-icons-round text-xs text-foreground">storefront</span>
                <span className="text-xs text-foreground">POI</span>
              </div>
            </div>
          </div>
        </div>

        {/* ── POI 바텀 시트 ── */}
        {selectedPoiData && (
          <div className="absolute bottom-24 left-4 right-4 bg-card rounded-3xl p-5 shadow-xl border border-border animate-in slide-in-from-bottom-4 z-40">
            <div className="flex items-start gap-4">
              <div className="w-14 h-14 rounded-2xl bg-muted flex items-center justify-center">
                <span className="material-icons-round text-2xl text-muted-foreground">
                  {poiIcon(selectedPoiData.category)}
                </span>
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-bold text-foreground">{selectedPoiData.name}</h3>
                <p className="text-sm text-muted-foreground">{selectedPoiData.category}</p>
                <p className="text-xs text-muted-foreground/60 mt-0.5 font-mono">
                  ({selectedPoiData.x.toFixed(2)}m, {selectedPoiData.y.toFixed(2)}m)
                </p>
              </div>
              <button onClick={() => setSelectedPoi(null)} className="p-1">
                <span className="material-icons-round text-muted-foreground">close</span>
              </button>
            </div>

            <div className="flex gap-3 mt-4">
              <button
                onClick={handleAddToGuide}
                disabled={!isActive || isTaskMode}
                className="flex-1 py-3 rounded-xl border border-border font-semibold text-foreground flex items-center justify-center gap-2 active-press-sm disabled:opacity-50"
              >
                <span className="material-icons-round text-lg">alt_route</span>
                Add to Guide
              </button>
              <button
                disabled={!isActive || isTaskMode}
                className="flex-1 py-3 rounded-xl bg-primary text-primary-foreground font-semibold flex items-center justify-center gap-2 shadow-md shadow-primary/30 active-press-sm disabled:opacity-50"
              >
                <span className="material-icons-round text-lg">shopping_bag</span>
                Order Pickup
              </button>
            </div>
            {isTaskMode && (
              <p className="text-xs text-muted-foreground text-center mt-2">Task 모드에서는 비활성화됩니다</p>
            )}
          </div>
        )}

        {/* Voice FAB */}
        <button
          onClick={() => setIsVoiceOpen(true)}
          className="fixed bottom-[118px] right-5 z-30 w-14 h-14 rounded-full bg-card/90 backdrop-blur-xl border border-border/50 shadow-xl ring-2 ring-primary/20 flex items-center justify-center transition-all duration-300 hover:shadow-2xl hover:scale-105 active:scale-90"
          title="Voice Command"
        >
          <span className="material-icons-round text-primary text-2xl">mic</span>
        </button>
        <VoiceCommandPanel open={isVoiceOpen} onClose={() => setIsVoiceOpen(false)} />

        <BottomNav />
      </div>
    </TooltipProvider>
  );
}
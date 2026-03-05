import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppStore } from '@/store/appStore';
import { BottomNav } from '@/components/layout/BottomNav';
import { VoiceCommandPanel } from '@/components/voice/VoiceCommandPanel';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

// 맵 물리 크기 (미터)
const MAP_WIDTH_M  = 2.45;
const MAP_HEIGHT_M = 2.0;
const MAP_OFFSET   = { left: 3.85, top: 4.65, right: 95.96, bottom: 95.12 };

/**
 * 미터 좌표 → 맵 컨테이너 내 % 위치 변환
 * ROS2 좌표계: x = 오른쪽 방향, y = 위쪽 방향
 * CSS: left % = x/width, top % = (height - y)/height  (y축 반전)
 */
function toMapPercent(x_m: number, y_m: number) {
  const innerW = MAP_OFFSET.right  - MAP_OFFSET.left;
  const innerH = MAP_OFFSET.bottom - MAP_OFFSET.top;
  const left = MAP_OFFSET.left + (x_m / MAP_WIDTH_M)                   * innerW;
  const top  = MAP_OFFSET.top  + ((MAP_HEIGHT_M - y_m) / MAP_HEIGHT_M) * innerH;
  return {
    left: `${Math.min(Math.max(left, 0), 100)}%`,
    top:  `${Math.min(Math.max(top,  0), 100)}%`,
  };
}

export default function MapPage() {
  const navigate = useNavigate();
  const { robot, pois, addToGuideQueue, sessionState, session, taskMission } = useAppStore();
  const [selectedPoi, setSelectedPoi] = useState<string | null>(null);
  const [isVoiceOpen, setIsVoiceOpen] = useState(false);

  const isActive   = sessionState === 'ACTIVE';
  const isTaskMode = isActive && session.type === 'TASK' && !!taskMission;
  const selectedPoiData = pois.find(p => p.id === selectedPoi);

  const handleAddToGuide = () => {
    if (selectedPoiData && !isTaskMode) {
      addToGuideQueue(selectedPoiData);
      setSelectedPoi(null);
    }
  };

  // POI 타입별 아이콘
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

          {/* 맵 컨테이너 — 2.5:2 비율 유지, 중앙 정렬 */}
          <div className="absolute inset-0 flex items-center justify-center p-4">
            <div
              className="relative rounded-2xl overflow-hidden border-2 border-border/60 shadow-xl"
              style={{
                /* 가로 2.5 : 세로 2 비율 */
                aspectRatio: '2.45 / 2',
                width: '100%',
                maxWidth: '380px',
                maxHeight: 'calc(100vh - 200px)',
              }}
            >
              {/* PGM 맵 이미지 배경 */}
              <img
                src="/map_end_end.png"
                alt="Mall Map"
                className="absolute inset-0 w-full h-full"
                style={{ imageRendering: 'pixelated', objectFit: 'fill' }}
                draggable={false}
              />

              {/* 반투명 오버레이 (가독성) */}
              <div className="absolute inset-0 bg-background/20" />

              {/* ── POI 마커 ── */}
              {pois.map((poi) => {
                const pos = toMapPercent(poi.x, poi.y);
                return (
                  <Tooltip key={poi.id}>
                    <TooltipTrigger asChild>
                      <button
                        onClick={() => setSelectedPoi(poi.id)}
                        className={`absolute flex flex-col items-center gap-0.5 transform -translate-x-1/2 -translate-y-1/2 transition-all z-10 ${
                          selectedPoi === poi.id ? 'scale-125 z-20' : 'hover:scale-110'
                        }`}
                        style={pos}
                      >
                        {/* 마커 원 */}
                        <div className={`w-7 h-7 rounded-full flex items-center justify-center shadow-md border-2 transition-colors ${
                          selectedPoi === poi.id
                            ? 'bg-primary border-primary text-primary-foreground'
                            : 'bg-card border-border text-foreground'
                        }`}>
                          <span className="material-icons-round text-xs">
                            {poiIcon(poi.category)}
                          </span>
                        </div>
                        {/* 이름 라벨 */}
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
                    {/* 펄스 링 */}
                    <div className="absolute inset-0 rounded-full bg-primary/30 animate-ping" />
                    {/* 이름 태그 */}
                    <div className="absolute -bottom-5 left-1/2 -translate-x-1/2 bg-foreground text-background text-[9px] font-bold px-2 py-0.5 rounded-full whitespace-nowrap">
                      {robot.name}
                    </div>
                  </div>
                </div>
              )}

              {/* ── 좌표 확인용 임시 마커 ── */}
              {[
                { label: '(0,0)',       x: 0,    y: 0 },
                { label: '(2.45,2)',    x: 2.45, y: 2 },
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
              ))}

              {/* ── 축척 표시 ── */}
              {/* <div className="absolute bottom-2 left-2 flex items-center gap-1">
                <div className="h-[2px] w-10 bg-foreground/60" />
                <span className="text-[9px] text-foreground/60 font-medium">0.5m</span>
              </div> */}

              {/* ── 좌표 원점 표시 (좌하단) ── */}
              <div className="absolute bottom-1.5 left-1.5 w-1.5 h-1.5 rounded-full bg-muted-foreground/40" />
            </div>
          </div>

          {/* ── 줌 컨트롤 ── */}
          <div className="absolute top-4 right-4 flex flex-col gap-2">
            <button className="w-10 h-10 rounded-full bg-card shadow-md flex items-center justify-center active-press-sm">
              <span className="material-icons-round text-foreground">add</span>
            </button>
            <button className="w-10 h-10 rounded-full bg-card shadow-md flex items-center justify-center active-press-sm">
              <span className="material-icons-round text-foreground">remove</span>
            </button>
            <button className="w-10 h-10 rounded-full bg-card shadow-md flex items-center justify-center active-press-sm mt-2">
              <span className="material-icons-round text-primary">my_location</span>
            </button>
          </div>

          {/* ── 범례 ── */}
          <div className="absolute top-4 left-4 bg-card/90 backdrop-blur-sm rounded-xl p-3 shadow-md">
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
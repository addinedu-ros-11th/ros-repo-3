import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppStore } from '@/store/appStore';
import { BottomNav } from '@/components/layout/BottomNav';
import { VoiceCommandPanel } from '@/components/voice/VoiceCommandPanel';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

export default function MapPage() {
  const navigate = useNavigate();
  const { robot, pois, addToGuideQueue, sessionState, session, taskMission } = useAppStore();
  const [selectedPoi, setSelectedPoi] = useState<string | null>(null);
  const [isVoiceOpen, setIsVoiceOpen] = useState(false);

  const isActive = sessionState === 'ACTIVE';
  const isTaskMode = isActive && session.type === 'TASK' && !!taskMission;
  const selectedPoiData = pois.find(p => p.id === selectedPoi);

  const handleAddToGuide = () => {
    if (selectedPoiData && !isTaskMode) {
      addToGuideQueue(selectedPoiData);
      setSelectedPoi(null);
    }
  };

  return (
    <TooltipProvider delayDuration={200}>
    <div className="fixed inset-0 z-10 flex flex-col max-w-[430px] mx-auto bg-background">
      <div className="flex-1 relative bg-muted map-pattern overflow-hidden">
        {/* Map Container */}
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="relative w-[320px] h-[400px] bg-card/50 rounded-3xl border-2 border-border/50">
            {/* POI Markers */}
            {pois.map((poi) => (
              <Tooltip key={poi.id}>
                <TooltipTrigger asChild>
                  <button
                    onClick={() => setSelectedPoi(poi.id)}
                    className={`absolute w-8 h-8 rounded-full flex items-center justify-center transition-all transform -translate-x-1/2 -translate-y-1/2 ${
                      selectedPoi === poi.id
                        ? 'bg-primary text-primary-foreground scale-125 shadow-lg z-20'
                        : 'bg-card text-foreground shadow-md hover:scale-110'
                    }`}
                    style={{ left: `${(poi.x / 320) * 100}%`, top: `${(poi.y / 180) * 100}%` }}
                  >
                    <span className="material-icons-round text-sm">place</span>
                  </button>
                </TooltipTrigger>
                <TooltipContent side="top" className="text-xs font-semibold">
                  {poi.name}
                </TooltipContent>
              </Tooltip>
            ))}

            {/* Robot Marker */}
            {isActive && robot && (
              <div 
                className="absolute transform -translate-x-1/2 -translate-y-1/2 z-30"
                style={{ left: `${(robot.location.x / 320) * 100}%`, top: `${(robot.location.y / 180) * 100}%` }}
              >
                <div className="relative">
                  <div className="w-10 h-10 rounded-full bg-primary flex items-center justify-center shadow-lg animate-pulse-ring">
                    <span className="material-icons-round text-primary-foreground text-xl">smart_toy</span>
                  </div>
                  <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 bg-foreground text-background text-[10px] font-bold px-2 py-0.5 rounded-full whitespace-nowrap">
                    {robot.name}
                  </div>
                </div>
              </div>
            )}

            {/* User Location */}
            <div 
              className="absolute transform -translate-x-1/2 -translate-y-1/2"
              style={{ left: '50%', top: '60%' }}
            >
              <div className="relative">
                <div className="w-4 h-4 rounded-full bg-blue-500 shadow-lg">
                  <div className="absolute inset-0 rounded-full bg-blue-500 animate-ping opacity-75" />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Controls */}
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

        {/* Legend */}
        <div className="absolute top-4 left-4 bg-card/90 backdrop-blur-sm rounded-xl p-3 shadow-md">
          <p className="text-xs font-bold text-muted-foreground mb-2">Legend</p>
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-primary" />
              <span className="text-xs text-foreground">Robot</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-blue-500" />
              <span className="text-xs text-foreground">You</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="material-icons-round text-xs text-muted-foreground">place</span>
              <span className="text-xs text-foreground">Store</span>
            </div>
          </div>
        </div>
      </div>

      {/* POI Bottom Sheet */}
      {selectedPoiData && (
        <div className="absolute bottom-24 left-4 right-4 bg-card rounded-3xl p-5 shadow-xl border border-border animate-in slide-in-from-bottom-4">
          <div className="flex items-start gap-4">
            <div className="w-14 h-14 rounded-2xl bg-muted flex items-center justify-center">
              <span className="material-icons-round text-2xl text-muted-foreground">storefront</span>
            </div>
            <div className="flex-1">
              <h3 className="text-lg font-bold text-foreground">{selectedPoiData.name}</h3>
              <p className="text-sm text-muted-foreground">{selectedPoiData.category}</p>
              <p className="text-xs text-primary mt-1">Open now</p>
            </div>
            <button 
              onClick={() => setSelectedPoi(null)}
              className="p-1"
            >
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
      {/* Voice Command FAB */}
      <button
        onClick={() => setIsVoiceOpen(true)}
        className="fixed bottom-[118px] right-5 z-30 w-14 h-14 rounded-full bg-card/90 dark:bg-card/90 backdrop-blur-xl border border-border/50 shadow-xl ring-2 ring-primary/20 flex items-center justify-center transition-all duration-300 hover:shadow-2xl hover:scale-105 active:scale-90"
        title="Voice Command"
      >
        <span className="material-icons-round text-primary text-2xl">mic</span>
      </button>
      <VoiceCommandPanel open={isVoiceOpen} onClose={() => setIsVoiceOpen(false)} />

      {/* Bottom Navigation */}
      <BottomNav />
    </div>
    </TooltipProvider>
  );
}

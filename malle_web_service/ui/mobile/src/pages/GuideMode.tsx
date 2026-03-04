import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppStore } from '@/store/appStore';
import { toast } from 'sonner';

export default function GuideMode() {
  const navigate = useNavigate();
  const [showAddList, setShowAddList] = useState(false);
  const { 
    guideQueue, 
    removeFromGuideQueue, 
    toggleGuideSelection, 
    clearGuideQueue,
    startGuide,
    addToGuideQueue,
    pois,
    sessionState,
    session,
    taskMission,
  } = useAppStore();

  const queuedPoiIds = new Set(guideQueue.map(item => Number(item.poiId)));
  const availablePois = pois.filter(p => !queuedPoiIds.has(Number(p.id)) && Number(p.id) > 9);

  const isActive = sessionState === 'ACTIVE';
  const isTaskMode = isActive && session.type === 'TASK' && !!taskMission;
  const selectedCount = guideQueue.filter(item => item.selected && item.status === 'PENDING').length;
  const hasQueue = guideQueue.length > 0;
  const canStart = selectedCount > 0;

  const handleStartGuide = () => {
    startGuide();
    navigate('/mode/guide/active');
  };

  const handleAddPoi = (poi: typeof pois[0]) => {
    addToGuideQueue(poi);
  };

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <button onClick={() => navigate('/mode')} className="flex items-center gap-1 text-primary mb-2">
            <span className="material-icons-round text-sm">arrow_back</span>
            <span className="text-sm font-medium">Back to Modes</span>
          </button>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Guide Queue</h1>
          <p className="text-muted-foreground text-sm mt-1">
            {hasQueue ? `${guideQueue.length} destinations in queue` : 'Add destinations to start navigation'}
          </p>
        </div>
        {!isTaskMode && (
          <button
            onClick={() => setShowAddList(!showAddList)}
            className="p-2 rounded-xl bg-primary text-primary-foreground active-press-sm"
          >
            <span className="material-icons-round">{showAddList ? 'close' : 'add'}</span>
          </button>
        )}
      </div>

      {/* Add from Store List */}
      {showAddList && (
        <div className="bg-card rounded-2xl border border-border overflow-hidden">
          <div className="px-4 py-3 border-b border-border">
            <h3 className="font-semibold text-foreground text-sm">Add Destination</h3>
          </div>
          {availablePois.length > 0 ? (
            <div className="divide-y divide-border max-h-64 overflow-y-auto">
              {availablePois.map((poi) => (
                <button
                  key={poi.id}
                  onClick={() => handleAddPoi(poi)}
                  className="w-full flex items-center gap-3 px-4 py-3 hover:bg-muted/50 transition-colors active-press-sm"
                >
                  <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                    <span className="material-icons-round text-primary text-sm">place</span>
                  </div>
                  <div className="flex-1 text-left">
                    <p className="font-medium text-foreground text-sm">{poi.name}</p>
                    <p className="text-xs text-muted-foreground">{poi.category} • Level 1</p>
                  </div>
                  <span className="material-icons-round text-primary text-xl">add_circle</span>
                </button>
              ))}
            </div>
          ) : (
            <p className="px-4 py-6 text-center text-sm text-muted-foreground">All destinations already in queue</p>
          )}
        </div>
      )}

      {/* Queue List */}
      {hasQueue ? (
        <div className="space-y-3">
          {guideQueue.map((item, index) => (
            <div 
              key={item.id}
              className={`bg-card rounded-2xl p-4 border transition-all ${
                item.status === 'DONE' 
                  ? 'border-emerald-200 bg-emerald-50 dark:bg-emerald-900/20 dark:border-emerald-800' 
                  : item.selected 
                    ? 'border-primary shadow-md' 
                    : 'border-border'
              }`}
            >
              <div className="flex items-center gap-4">
                {/* Checkbox */}
                <button
                  onClick={() => toggleGuideSelection(item.id)}
                  disabled={item.status !== 'PENDING' || isTaskMode}
                  className={`w-6 h-6 rounded-lg border-2 flex items-center justify-center transition-all ${
                    item.status === 'DONE'
                      ? 'bg-emerald-500 border-emerald-500'
                      : item.selected
                        ? 'bg-primary border-primary'
                        : 'border-muted-foreground/30 hover:border-primary'
                  }`}
                >
                  {(item.selected || item.status === 'DONE') && (
                    <span className="material-icons-round text-white text-sm">check</span>
                  )}
                </button>

                {/* Order Number */}
                <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center">
                  <span className="text-sm font-bold text-muted-foreground">{index + 1}</span>
                </div>

                {/* Info */}
                <div className="flex-1">
                  <h3 className={`font-semibold ${item.status === 'DONE' ? 'text-emerald-600 dark:text-emerald-400' : 'text-foreground'}`}>
                    {item.poiName}
                  </h3>
                  <p className="text-xs text-muted-foreground">{item.floor} • ~{item.estimatedTime} min</p>
                </div>

                {/* Status/Delete */}
                {item.status === 'DONE' ? (
                  <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400 bg-emerald-100 dark:bg-emerald-900/50 px-2 py-1 rounded-full">
                    Completed
                  </span>
                ) : (
                  !isTaskMode && (
                    <button
                      onClick={() => removeFromGuideQueue(item.id)}
                      className="p-2 rounded-full hover:bg-destructive/10 transition-colors"
                    >
                      <span className="material-icons-round text-destructive text-xl">delete</span>
                    </button>
                  )
                )}
              </div>
            </div>
          ))}

          {/* Actions */}
          <div className="flex gap-3 pt-4">
            {!isTaskMode && (
              <button
                onClick={clearGuideQueue}
                className="flex-1 py-3 rounded-xl border border-border text-muted-foreground font-semibold hover:bg-muted transition-colors active-press-sm"
              >
                Clear All
              </button>
            )}
            <button
              onClick={handleStartGuide}
              disabled={!canStart || !isActive}
              className={`${isTaskMode ? 'w-full' : 'flex-1'} py-3 rounded-xl bg-primary text-primary-foreground font-semibold shadow-lg shadow-primary/30 hover:bg-primary/90 transition-colors active-press-sm disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2`}
            >
              <span className="material-icons-round">play_arrow</span>
              Start Guide ({selectedCount})
            </button>
          </div>
        </div>
      ) : (
        <div className="bg-muted rounded-3xl p-8 text-center">
          <div className="w-20 h-20 rounded-full bg-background mx-auto flex items-center justify-center mb-4">
            <span className="material-icons-round text-4xl text-muted-foreground">alt_route</span>
          </div>
          <h3 className="font-bold text-lg text-foreground mb-2">No Destinations</h3>
          <p className="text-sm text-muted-foreground mb-6">
            Tap + above to add from the store list, or open the map
          </p>
          <div className="flex gap-3 justify-center">
            <button
              onClick={() => setShowAddList(true)}
              className="px-5 py-3 rounded-xl border border-border text-foreground font-semibold hover:bg-background transition-colors active-press-sm"
            >
              Store List
            </button>
            <button
              onClick={() => navigate('/map')}
              className="px-5 py-3 rounded-xl bg-primary text-primary-foreground font-semibold shadow-lg shadow-primary/30 active-press-sm"
            >
              Open Map
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

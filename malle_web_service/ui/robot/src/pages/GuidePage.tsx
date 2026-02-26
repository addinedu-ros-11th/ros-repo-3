import { useRobotStore } from '@/stores/robotStore';
import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { stores } from '@/data/stores';

export function GuidePage() {
  const {
    guide,
    addToGuideQueue,
    removeFromGuideQueue,
    clearGuideQueue,
    toggleGuideItemSelection,
    selectAllGuideItems,
    startGuide,
    stopGuide,
    advanceGuide,
    setGuideItemStatus,
    setRobotStatus,
  } = useRobotStore();

  const navigate = useNavigate();
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [showArrivalDialog, setShowArrivalDialog] = useState(false);
  const [showWaitingOverlay, setShowWaitingOverlay] = useState(false);
  const [waitPin, setWaitPin] = useState('');
  const [waitPinVerified, setWaitPinVerified] = useState(false);

  const selectedCount = guide.queue.filter(item => item.selected).length;
  const selectedItems = guide.queue.filter(item => item.selected);
  const currentDestination = guide.isExecuting
    ? selectedItems[guide.currentDestinationIndex]
    : null;
  const isLastStop = guide.isExecuting && guide.currentDestinationIndex >= selectedItems.length - 1;

  const handleAddDestination = (store: typeof stores[0]) => {
    addToGuideQueue({
      poiId: store.id,
      poiName: store.name,
      floor: store.location,
      estimatedTime: Math.floor(Math.random() * 5) + 2,
    });
    setShowAddDialog(false);
  };

  const handleStartGuide = () => {
    if (selectedCount > 0) {
      startGuide();
      setRobotStatus('MOVING');
      
      setTimeout(() => {
        setRobotStatus('WAITING');
        const { guide: latestGuide } = useRobotStore.getState();
        const items = latestGuide.queue.filter(item => item.selected);
        if (items[0]) {
          setGuideItemStatus(items[0].id, 'ARRIVED');
        }
        setShowArrivalDialog(true);
      }, 3000);
    }
  };

  const handleArrivalAction = (action: 'wait' | 'next' | 'cancel' | 'end' | 'addMore') => {
    setShowArrivalDialog(false);
    
    if (action === 'cancel' || action === 'end') {
      if (currentDestination) {
        setGuideItemStatus(currentDestination.id, 'DONE');
      }
      stopGuide();
      setRobotStatus('IDLE');
      return;
    }

    if (action === 'addMore') {
      // Keep guide running but let user add more
      setShowAddDialog(true);
      return;
    }

    if (action === 'wait') {
      setRobotStatus('WAITING');
      setShowWaitingOverlay(true);
      setWaitPin('');
      setWaitPinVerified(false);
      return;
    }

    if (action === 'next') {
      if (currentDestination) {
        setGuideItemStatus(currentDestination.id, 'DONE');
      }
      advanceGuide();
      setRobotStatus('MOVING');

      const remaining = selectedItems.filter(item => item.status !== 'DONE');
      if (remaining.length > 1) {
        setTimeout(() => {
          setRobotStatus('WAITING');
          // 클로저 대신 최신 store 상태 직접 참조
          const { guide: latestGuide } = useRobotStore.getState();
          const nextItems = latestGuide.queue.filter(item => item.selected);
          const nextItem = nextItems[latestGuide.currentDestinationIndex];
          if (nextItem) {
            setGuideItemStatus(nextItem.id, 'ARRIVED');
          }
          setShowArrivalDialog(true);
        }, 3000);
      } else {
        setTimeout(() => {
          stopGuide();
          setRobotStatus('IDLE');
        }, 1000);
      }
    }
  };

  const handleWaitPinKey = useCallback((digit: string) => {
    if (waitPin.length < 4) {
      const newPin = waitPin + digit;
      setWaitPin(newPin);
      if (newPin.length === 4) {
        setTimeout(() => {
          setWaitPinVerified(true);
        }, 500);
      }
    }
  }, [waitPin]);

  const handleWaitPinBackspace = useCallback(() => {
    setWaitPin(prev => prev.slice(0, -1));
  }, []);

  const handleWaitNextStop = () => {
    setShowWaitingOverlay(false);
    if (currentDestination) {
      setGuideItemStatus(currentDestination.id, 'DONE');
    }
    advanceGuide();
    setRobotStatus('MOVING');

    const remaining = selectedItems.filter(item => item.status !== 'DONE');
    if (remaining.length > 1) {
      setTimeout(() => {
        setRobotStatus('WAITING');
        // 클로저 대신 최신 store 상태 직접 참조
        const { guide: latestGuide } = useRobotStore.getState();
        const nextItems = latestGuide.queue.filter(item => item.selected);
        const nextItem = nextItems[latestGuide.currentDestinationIndex];
        if (nextItem) {
          setGuideItemStatus(nextItem.id, 'ARRIVED');
        }
        setShowArrivalDialog(true);
      }, 3000);
    } else {
      setTimeout(() => {
        stopGuide();
        setRobotStatus('IDLE');
      }, 1000);
    }
  };

  const handleWaitEndGuide = () => {
    setShowWaitingOverlay(false);
    if (currentDestination) {
      setGuideItemStatus(currentDestination.id, 'DONE');
    }
    stopGuide();
    setRobotStatus('IDLE');
  };

  const handleWaitAddMore = () => {
    setShowWaitingOverlay(false);
    setShowAddDialog(true);
  };

  const handleDeleteSelected = () => {
    guide.queue.filter(item => item.selected).forEach(item => {
      removeFromGuideQueue(item.id);
    });
  };

  if (guide.isExecuting) {
    const remainingCount = selectedItems.length - guide.currentDestinationIndex - 1;

    return (
      <div>
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-page-title">Guide Mode</h1>
          <button onClick={() => { stopGuide(); setRobotStatus('IDLE'); }} className="btn-danger">
            <span className="material-icons-round mr-2 align-middle">close</span>
            End Guide
          </button>
        </div>

        <div className="max-w-2xl mx-auto">
          <div className="robot-card-blue text-center py-12">
            <div className="absolute -right-10 -top-10 w-48 h-48 bg-white/10 rounded-full blur-3xl" />
            <div className="relative z-10">
              <h2 className="text-3xl font-bold text-white mb-2">
                {currentDestination?.poiName || 'Destination'}
              </h2>
              <p className="text-white/80 text-lg mb-6">{currentDestination?.floor}</p>
              
              <div className="inline-flex items-center space-x-2 bg-white/20 rounded-full px-6 py-3 mb-6">
                <span className="material-icons-round text-white animate-pulse">
                  {currentDestination?.status === 'ARRIVED' ? 'place' : 'directions'}
                </span>
                <span className="font-semibold text-white">
                  {currentDestination?.status === 'ARRIVED' ? 'Arrived' : 'Moving'}
                </span>
              </div>
              
              <p className="text-white/70">
                {remainingCount > 0 ? `${remainingCount} stops remaining` : 'Last stop'}
              </p>
            </div>
          </div>

          {/* Progress Stepper */}
          <div className="flex items-center justify-center mt-8 space-x-2">
            {selectedItems.map((item, index) => (
              <div key={item.id} className="flex items-center">
                <div className="flex flex-col items-center">
                  <div
                    className={`w-4 h-4 rounded-full ${
                      item.status === 'DONE'
                        ? 'bg-emerald-500'
                        : index === guide.currentDestinationIndex
                        ? 'bg-primary ring-4 ring-primary/30'
                        : 'bg-slate-300 dark:bg-slate-600'
                    }`}
                  />
                  {item.status === 'DONE' && (
                    <span className="text-xs text-emerald-500 font-medium mt-1">Completed</span>
                  )}
                </div>
                {index < selectedItems.length - 1 && (
                  <div className={`w-8 h-1 mx-1 ${item.status === 'DONE' ? 'bg-emerald-500' : 'bg-slate-300 dark:bg-slate-600'}`} />
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Arrival Dialog */}
        {showArrivalDialog && (
          <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center">
            <div className="bg-card rounded-2xl p-6 w-96 shadow-2xl animate-scale-in">
              {isLastStop ? (
                <>
                  <div className="text-center mb-6">
                    <div className="w-16 h-16 rounded-full bg-emerald-100 dark:bg-emerald-900/30 mx-auto mb-4 flex items-center justify-center">
                      <span className="material-icons-round text-emerald-500 text-3xl">flag</span>
                    </div>
                    <h3 className="text-lg font-bold text-foreground mb-1">
                      Arrived at {currentDestination?.poiName}
                    </h3>
                    <p className="text-muted-foreground">This is your last stop</p>
                  </div>
                  <div className="space-y-3">
                    <button onClick={() => handleArrivalAction('wait')} className="w-full btn-secondary">
                      <span className="material-icons-round mr-2 align-middle">schedule</span>
                      Wait
                    </button>
                    <button onClick={() => handleArrivalAction('end')} className="w-full btn-primary">
                      <span className="material-icons-round mr-2 align-middle">check_circle</span>
                      End Guide
                    </button>
                    <button onClick={() => handleArrivalAction('addMore')} className="w-full btn-ghost text-primary">
                      <span className="material-icons-round mr-2 align-middle">add</span>
                      Add Destination
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <h3 className="text-lg font-bold text-foreground mb-2">
                    Arrived at {currentDestination?.poiName}
                  </h3>
                  <p className="text-muted-foreground mb-6">What's next?</p>
                  <div className="space-y-3">
                    <button onClick={() => handleArrivalAction('wait')} className="w-full btn-secondary">
                      <span className="material-icons-round mr-2 align-middle">schedule</span>
                      Wait
                    </button>
                    <button onClick={() => handleArrivalAction('next')} className="w-full btn-primary">
                      <span className="material-icons-round mr-2 align-middle">arrow_forward</span>
                      Next Stop
                    </button>
                    <button onClick={() => handleArrivalAction('cancel')} className="w-full btn-ghost text-destructive">
                      Cancel
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        )}

        {/* Waiting Overlay with PIN */}
        {showWaitingOverlay && (
          <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center">
            <div className="overlay-card w-[500px] text-center">
              {!waitPinVerified ? (
                <>
                  <div className="w-16 h-16 rounded-full bg-amber-100 dark:bg-amber-900/30 mx-auto mb-4 flex items-center justify-center">
                    <span className="material-icons-round text-amber-500 text-3xl animate-pulse">schedule</span>
                  </div>
                  <h2 className="text-2xl font-bold text-foreground mb-1">Waiting</h2>
                  <p className="text-muted-foreground mb-1">
                    <span className="font-semibold text-foreground">{currentDestination?.poiName}</span> · {currentDestination?.floor}
                  </p>
                  <p className="text-sm text-muted-foreground mb-8">Enter PIN from the app to continue</p>

                  {/* PIN Display */}
                  <div className="flex justify-center space-x-3 mb-8">
                    {[0, 1, 2, 3].map((index) => (
                      <div
                        key={index}
                        className={waitPin.length > index ? 'pin-box-filled' : 'pin-box'}
                      >
                        {waitPin[index] ? '•' : ''}
                      </div>
                    ))}
                  </div>

                  {/* Numeric Keypad */}
                  <div className="grid grid-cols-3 gap-3 max-w-xs mx-auto mb-6">
                    {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((digit) => (
                      <button
                        key={digit}
                        onClick={() => handleWaitPinKey(String(digit))}
                        className="keypad-btn"
                      >
                        {digit}
                      </button>
                    ))}
                    <div />
                    <button onClick={() => handleWaitPinKey('0')} className="keypad-btn">0</button>
                    <button onClick={handleWaitPinBackspace} className="keypad-btn">
                      <span className="material-icons-round">backspace</span>
                    </button>
                  </div>

                  <p className="text-xs text-muted-foreground">Demo: Enter any 4 digits</p>
                </>
              ) : (
                <>
                  <div className="w-16 h-16 rounded-full bg-emerald-100 dark:bg-emerald-900/30 mx-auto mb-4 flex items-center justify-center">
                    <span className="material-icons-round text-emerald-500 text-3xl">check</span>
                  </div>
                  <h2 className="text-2xl font-bold text-foreground mb-1">PIN Verified</h2>
                  <p className="text-muted-foreground mb-8">
                    <span className="font-semibold text-foreground">{currentDestination?.poiName}</span> · {currentDestination?.floor}
                  </p>

                  <div className="space-y-3">
                    {isLastStop ? (
                      <>
                        <button onClick={handleWaitEndGuide} className="w-full btn-primary py-4 text-lg">
                          <span className="material-icons-round mr-2 align-middle">check_circle</span>
                          End Guide
                        </button>
                        <button onClick={handleWaitAddMore} className="w-full btn-secondary py-3">
                          <span className="material-icons-round mr-2 align-middle">add</span>
                          Add Destination
                        </button>
                      </>
                    ) : (
                      <>
                        <button onClick={handleWaitNextStop} className="w-full btn-primary py-4 text-lg">
                          <span className="material-icons-round mr-2 align-middle">arrow_forward</span>
                          Next Stop
                        </button>
                        <button onClick={handleWaitEndGuide} className="w-full btn-ghost text-destructive py-3">
                          End Guide
                        </button>
                      </>
                    )}
                  </div>
                </>
              )}
            </div>
          </div>
        )}

        {/* Add Destination Dialog (can appear during execution) */}
        {showAddDialog && (
          <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center">
            <div className="bg-card rounded-2xl p-6 w-[500px] max-h-[80vh] shadow-2xl animate-scale-in">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-bold text-foreground">Add Destination</h3>
                <button onClick={() => setShowAddDialog(false)} className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800">
                  <span className="material-icons-round text-slate-500">close</span>
                </button>
              </div>
              <div className="space-y-2 max-h-[400px] overflow-y-auto hide-scrollbar">
                {stores.filter(s => s.open).map((store) => (
                  <button
                    key={store.id}
                    onClick={() => handleAddDestination(store)}
                    className="w-full flex items-center space-x-3 p-4 rounded-xl border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors text-left"
                  >
                    <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
                      <span className="material-icons-round text-primary">{store.icon}</span>
                    </div>
                    <div>
                      <p className="font-semibold text-foreground">{store.name}</p>
                      <p className="text-sm text-muted-foreground">{store.location}</p>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  // Queue Builder View
  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center space-x-3">
          <button onClick={() => navigate('/mode')} className="btn-ghost p-2">
            <span className="material-icons-round">arrow_back</span>
          </button>
          <h1 className="text-page-title">Guide Mode</h1>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-8">
        {/* Queue List */}
        <div className="robot-card-white">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-bold text-foreground">Destination Queue</h3>
            <div className="flex items-center space-x-2">
              {guide.queue.length > 0 && (
                <>
                  <button
                    onClick={() => selectAllGuideItems(selectedCount !== guide.queue.length)}
                    className="text-sm text-primary font-medium hover:underline"
                  >
                    {selectedCount === guide.queue.length ? 'Deselect All' : 'Select All'}
                  </button>
                  <button onClick={clearGuideQueue} className="text-sm text-destructive font-medium hover:underline ml-4">
                    Clear All
                  </button>
                </>
              )}
            </div>
          </div>

          {guide.queue.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <span className="material-icons-round text-4xl mb-2">alt_route</span>
              <p>No destinations added</p>
              <p className="text-sm">Add destinations to create a guide route</p>
            </div>
          ) : (
            <div className="space-y-2 mb-4">
              {guide.queue.map((item) => (
                <div
                  key={item.id}
                  className={`flex items-center space-x-3 p-3 rounded-xl border transition-colors ${
                    item.status === 'DONE'
                      ? 'border-emerald-300 dark:border-emerald-700 bg-emerald-50 dark:bg-emerald-900/20'
                      : item.selected
                      ? 'border-primary bg-primary/5'
                      : 'border-slate-200 dark:border-slate-700'
                  }`}
                >
                  <button
                    onClick={() => toggleGuideItemSelection(item.id)}
                    className={`w-6 h-6 rounded-lg border-2 flex items-center justify-center ${
                      item.selected
                        ? 'bg-primary border-primary'
                        : 'border-slate-300 dark:border-slate-600'
                    }`}
                  >
                    {item.selected && <span className="material-icons-round text-white text-sm">check</span>}
                  </button>
                  <div className="flex-1">
                    <div className="flex items-center space-x-2">
                      <p className="font-semibold text-foreground">{item.poiName}</p>
                      {item.status === 'DONE' && (
                        <span className="text-xs font-bold text-emerald-600 dark:text-emerald-400 bg-emerald-100 dark:bg-emerald-900/40 px-2 py-0.5 rounded-full">
                          Completed
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-muted-foreground">{item.floor} • ~{item.estimatedTime} min</p>
                  </div>
                  <button
                    onClick={() => removeFromGuideQueue(item.id)}
                    className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800"
                  >
                    <span className="material-icons-round text-slate-400">delete</span>
                  </button>
                </div>
              ))}
            </div>
          )}

          {selectedCount > 0 && (
            <button onClick={handleDeleteSelected} className="text-sm text-destructive font-medium hover:underline mb-4">
              Delete Selected ({selectedCount})
            </button>
          )}

          <div className="flex space-x-3">
            <button onClick={() => setShowAddDialog(true)} className="flex-1 btn-secondary">
              <span className="material-icons-round mr-2 align-middle">add</span>
              Add Destination
            </button>
            <button
              onClick={handleStartGuide}
              disabled={selectedCount === 0}
              className="flex-1 btn-primary disabled:opacity-50"
            >
              <span className="material-icons-round mr-2 align-middle">play_arrow</span>
              Start Guide
            </button>
          </div>
        </div>

        {/* Route Preview */}
        <div className="robot-card-white">
          <h3 className="text-lg font-bold text-foreground mb-4">Optimal Route Preview</h3>
          {guide.queue.length === 0 ? (
            <div className="aspect-video bg-slate-100 dark:bg-slate-800 rounded-2xl map-grid flex items-center justify-center">
              <div className="text-center text-muted-foreground">
                <span className="material-icons-round text-4xl mb-2">map</span>
                <p>0 destinations</p>
              </div>
            </div>
          ) : (
            <div className="bg-slate-100 dark:bg-slate-800 rounded-2xl p-6 min-h-[200px]">
              <div className="relative">
                {guide.queue.map((item, index) => (
                  <div key={item.id} className="flex items-start animate-fade-in" style={{ animationDelay: `${index * 0.1}s` }}>
                    {/* Connector line */}
                    <div className="flex flex-col items-center mr-4">
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                        item.status === 'DONE'
                          ? 'bg-emerald-500 text-white'
                          : 'bg-primary text-white'
                      }`}>
                        {item.status === 'DONE' ? (
                          <span className="material-icons-round text-sm">check</span>
                        ) : (
                          <span className="text-sm font-bold">{index + 1}</span>
                        )}
                      </div>
                      {index < guide.queue.length - 1 && (
                        <div className="w-0.5 h-8 bg-primary/30 my-1 relative overflow-hidden">
                          <div className="absolute inset-0 bg-primary animate-pulse" style={{ animationDelay: `${index * 0.3}s` }} />
                        </div>
                      )}
                    </div>
                    {/* Location info */}
                    <div className="pb-6">
                      <p className={`font-semibold text-sm ${item.status === 'DONE' ? 'text-emerald-600 dark:text-emerald-400 line-through' : 'text-foreground'}`}>
                        {item.poiName}
                      </p>
                      <p className="text-xs text-muted-foreground">{item.floor} • ~{item.estimatedTime} min</p>
                    </div>
                  </div>
                ))}
                {/* Finish flag */}
                <div className="flex items-center animate-fade-in" style={{ animationDelay: `${guide.queue.length * 0.1}s` }}>
                  <div className="flex flex-col items-center mr-4">
                    <div className="w-8 h-8 rounded-full bg-slate-300 dark:bg-slate-600 flex items-center justify-center">
                      <span className="material-icons-round text-sm text-slate-500 dark:text-slate-400">flag</span>
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground font-medium">End of route</p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Add Destination Dialog */}
      {showAddDialog && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center">
          <div className="bg-card rounded-2xl p-6 w-[500px] max-h-[80vh] shadow-2xl animate-scale-in">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-foreground">Add Destination</h3>
              <button onClick={() => setShowAddDialog(false)} className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800">
                <span className="material-icons-round text-slate-500">close</span>
              </button>
            </div>
            <div className="space-y-2 max-h-[400px] overflow-y-auto hide-scrollbar">
              {stores.filter(s => s.open).map((store) => (
                <button
                  key={store.id}
                  onClick={() => handleAddDestination(store)}
                  className="w-full flex items-center space-x-3 p-4 rounded-xl border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors text-left"
                >
                  <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
                    <span className="material-icons-round text-primary">{store.icon}</span>
                  </div>
                  <div>
                    <p className="font-semibold text-foreground">{store.name}</p>
                    <p className="text-sm text-muted-foreground">{store.location}</p>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

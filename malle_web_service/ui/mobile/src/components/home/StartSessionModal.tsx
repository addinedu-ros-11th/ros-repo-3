import { useState } from 'react';
import { useAppStore, SessionType, TaskMissionType, POI } from '@/store/appStore';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';

interface StartSessionModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const timeOptions = [
  { label: '30 min', value: 30 },
  { label: '1 hour', value: 60 },
  { label: '1h 30m', value: 90 },
  { label: '2 hours', value: 120 },
];

const storeProducts: Record<string, { name: string; price: number }[]> = {
  zara: [
    { name: 'Linen Blend Shirt', price: 45.90 },
    { name: 'Pleated Trousers', price: 59.90 },
    { name: 'Cotton T-Shirt', price: 19.90 },
  ],
  nike: [
    { name: 'Air Zoom Pegasus', price: 120.00 },
    { name: 'Running Socks (3pk)', price: 18.00 },
    { name: 'Dri-FIT Headband', price: 12.00 },
  ],
  apple: [
    { name: 'USB-C Charge Cable', price: 19.00 },
    { name: 'AirPods Case', price: 29.00 },
  ],
};

type WizardStep = 'type' | 'mission-type' | 'mission-detail' | 'mission-summary';

export function StartSessionModal({ isOpen, onClose }: StartSessionModalProps) {
  const { startFindingRobot, setTaskMission, stores, pois } = useAppStore();
  const [sessionType, setSessionType] = useState<SessionType>('TIME');
  const [selectedDuration, setSelectedDuration] = useState(60);
  const [isLoading, setIsLoading] = useState(false);

  // Task mode state
  const [wizardStep, setWizardStep] = useState<WizardStep>('type');
  const [missionType, setMissionType] = useState<TaskMissionType>('GUIDE');
  const [selectedPoi, setSelectedPoi] = useState<POI | null>(null);
  const [selectedStore, setSelectedStore] = useState<string | null>(null);
  const [selectedItems, setSelectedItems] = useState<{ name: string; quantity: number; price: number; productId?: number }[]>([]);
  const [poiSearch, setPoiSearch] = useState('');

  const resetWizard = () => {
    setWizardStep('type');
    setMissionType('GUIDE');
    setSelectedPoi(null);
    setSelectedStore(null);
    setSelectedItems([]);
    setPoiSearch('');
    setSessionType('TIME');
    setSelectedDuration(60);
    setIsLoading(false);
  };

  const handleClose = () => {
    resetWizard();
    onClose();
  };

  const handleStartTime = () => {
    setIsLoading(true);
    startFindingRobot('TIME', selectedDuration);
    setIsLoading(false);
    handleClose();
  };

  const handleStartTask = () => {
    setIsLoading(true);

    // Save mission info
    if (missionType === 'GUIDE' && selectedPoi) {
      setTaskMission({ type: 'GUIDE', destinationPoi: selectedPoi });
    } else if (missionType === 'PICKUP' && selectedStore) {
      const store = stores.find(s => s.id === selectedStore);
      setTaskMission({
        type: 'PICKUP',
        storeId: selectedStore,
        storeName: store?.name || '',
        items: selectedItems,
      });
    }

    startFindingRobot('TASK', 0);
    setIsLoading(false);
    handleClose();
  };

  const handleAddItem = (product: { name: string; price: number; productId?: number }) => {
    const existing = selectedItems.find(i => i.name === product.name);
    if (existing) {
      setSelectedItems(items =>
        items.map(i => i.name === product.name ? { ...i, quantity: i.quantity + 1 } : i)
      );
    } else {
      setSelectedItems(items => [...items, { ...product, quantity: 1 }]);
    }
  };

  const handleNext = () => {
    if (wizardStep === 'type' && sessionType === 'TASK') {
      setWizardStep('mission-type');
    } else if (wizardStep === 'mission-type') {
      setWizardStep('mission-detail');
    } else if (wizardStep === 'mission-detail') {
      setWizardStep('mission-summary');
    }
  };

  const handleBack = () => {
    if (wizardStep === 'mission-type') setWizardStep('type');
    else if (wizardStep === 'mission-detail') setWizardStep('mission-type');
    else if (wizardStep === 'mission-summary') setWizardStep('mission-detail');
  };

  const filteredPois = pois.filter(p =>
    p.name.toLowerCase().includes(poiSearch.toLowerCase())
  );

  const availableStores = stores.filter(s => s.open && storeProducts[s.id]);

  const canProceedDetail = missionType === 'GUIDE' ? !!selectedPoi : (!!selectedStore && selectedItems.length > 0);

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="max-w-[360px] rounded-3xl p-0 overflow-hidden max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className="bg-gradient-to-br from-primary to-blue-600 p-6 text-white shrink-0">
          {wizardStep !== 'type' && (
            <button onClick={handleBack} className="flex items-center gap-1 text-white/70 mb-2 text-sm">
              <span className="material-icons-round text-sm">arrow_back</span>
              Back
            </button>
          )}
          <DialogHeader>
            <DialogTitle className="text-white text-xl">
              {wizardStep === 'type' && 'Choose Session Type'}
              {wizardStep === 'mission-type' && 'Choose Mission'}
              {wizardStep === 'mission-detail' && (missionType === 'GUIDE' ? 'Select Destination' : 'Select Items')}
              {wizardStep === 'mission-summary' && 'Mission Summary'}
            </DialogTitle>
          </DialogHeader>
          <p className="text-white/70 text-sm mt-2">
            {wizardStep === 'type' && 'Select how you want to be charged for your session'}
            {wizardStep === 'mission-type' && 'What should the robot do for you?'}
            {wizardStep === 'mission-detail' && missionType === 'GUIDE' && 'Choose where the robot should guide you'}
            {wizardStep === 'mission-detail' && missionType === 'PICKUP' && 'Select a store and items to pickup'}
            {wizardStep === 'mission-summary' && 'Review your task before finding a robot'}
          </p>
        </div>

        {/* Content */}
        <div className="p-6 space-y-5 overflow-y-auto hide-scrollbar flex-1">

          {/* Step 1: Session Type */}
          {wizardStep === 'type' && (
            <>
              <div className="grid grid-cols-2 gap-3">
                <button
                  onClick={() => setSessionType('TASK')}
                  className={`p-4 rounded-2xl border-2 transition-all active-press ${
                    sessionType === 'TASK'
                      ? 'border-primary bg-primary/5'
                      : 'border-border hover:border-muted-foreground/30'
                  }`}
                >
                  <span className="material-icons-round text-2xl text-primary mb-2">task_alt</span>
                  <h3 className="font-bold">Task</h3>
                  <p className="text-xs text-muted-foreground mt-1">Per mission</p>
                </button>
                <button
                  onClick={() => setSessionType('TIME')}
                  className={`p-4 rounded-2xl border-2 transition-all active-press ${
                    sessionType === 'TIME'
                      ? 'border-primary bg-primary/5'
                      : 'border-border hover:border-muted-foreground/30'
                  }`}
                >
                  <span className="material-icons-round text-2xl text-primary mb-2">schedule</span>
                  <h3 className="font-bold">Time</h3>
                  <p className="text-xs text-muted-foreground mt-1">30min blocks</p>
                </button>
              </div>

              {/* TIME: Duration Selection */}
              {sessionType === 'TIME' && (
                <div>
                  <p className="text-sm font-medium text-muted-foreground mb-3">Select Duration</p>
                  <div className="grid grid-cols-4 gap-2">
                    {timeOptions.map((option) => (
                      <button
                        key={option.value}
                        onClick={() => setSelectedDuration(option.value)}
                        className={`py-3 rounded-xl text-sm font-semibold transition-all active-press-sm ${
                          selectedDuration === option.value
                            ? 'bg-primary text-white shadow-md shadow-primary/30'
                            : 'bg-muted text-muted-foreground hover:bg-muted/80'
                        }`}
                      >
                        {option.label}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Start/Next Button */}
              {sessionType === 'TIME' ? (
                <button
                  onClick={handleStartTime}
                  disabled={isLoading}
                  className="w-full bg-primary text-white py-4 rounded-2xl font-bold shadow-lg shadow-primary/30 hover:bg-primary/90 transition-colors active-press-sm disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {isLoading ? (
                    <>
                      <span className="material-icons-round animate-spin">sync</span>
                      Finding your robot...
                    </>
                  ) : (
                    <>
                      <span className="material-icons-round">smart_toy</span>
                      Find Robot
                    </>
                  )}
                </button>
              ) : (
                <button
                  onClick={handleNext}
                  className="w-full bg-primary text-white py-4 rounded-2xl font-bold shadow-lg shadow-primary/30 hover:bg-primary/90 transition-colors active-press-sm flex items-center justify-center gap-2"
                >
                  <span className="material-icons-round">arrow_forward</span>
                  Define Mission
                </button>
              )}
            </>
          )}

          {/* Step 2: Mission Type (Task only) */}
          {wizardStep === 'mission-type' && (
            <>
              <div className="space-y-3">
                <button
                  onClick={() => setMissionType('GUIDE')}
                  className={`w-full p-4 rounded-2xl border-2 transition-all active-press text-left flex items-center gap-4 ${
                    missionType === 'GUIDE'
                      ? 'border-primary bg-primary/5'
                      : 'border-border hover:border-muted-foreground/30'
                  }`}
                >
                  <div className="w-12 h-12 rounded-xl bg-blue-100 dark:bg-blue-900/40 flex items-center justify-center">
                    <span className="material-icons-round text-xl text-primary">alt_route</span>
                  </div>
                  <div>
                    <h3 className="font-bold text-foreground">Guide</h3>
                    <p className="text-xs text-muted-foreground mt-0.5">로봇이 목적지까지 안내합니다</p>
                  </div>
                </button>

                <button
                  onClick={() => setMissionType('PICKUP')}
                  className={`w-full p-4 rounded-2xl border-2 transition-all active-press text-left flex items-center gap-4 ${
                    missionType === 'PICKUP'
                      ? 'border-primary bg-primary/5'
                      : 'border-border hover:border-muted-foreground/30'
                  }`}
                >
                  <div className="w-12 h-12 rounded-xl bg-orange-100 dark:bg-orange-900/40 flex items-center justify-center">
                    <span className="material-icons-round text-xl text-orange-500">shopping_bag</span>
                  </div>
                  <div>
                    <h3 className="font-bold text-foreground">Pickup</h3>
                    <p className="text-xs text-muted-foreground mt-0.5">로봇이 매장에서 물건을 픽업합니다</p>
                  </div>
                </button>
              </div>

              <button
                onClick={handleNext}
                className="w-full bg-primary text-white py-4 rounded-2xl font-bold shadow-lg shadow-primary/30 hover:bg-primary/90 transition-colors active-press-sm flex items-center justify-center gap-2"
              >
                <span className="material-icons-round">arrow_forward</span>
                Next
              </button>
            </>
          )}

          {/* Step 3: Mission Detail */}
          {wizardStep === 'mission-detail' && (
            <>
              {missionType === 'GUIDE' && (
                <div className="space-y-3">
                  {/* Search */}
                  <div className="relative">
                    <span className="material-icons-round absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground text-lg">search</span>
                    <input
                      type="text"
                      placeholder="Search destination..."
                      value={poiSearch}
                      onChange={(e) => setPoiSearch(e.target.value)}
                      className="w-full pl-10 pr-4 py-3 rounded-xl bg-muted text-sm font-medium outline-none focus:ring-2 focus:ring-primary/50"
                    />
                  </div>

                  {/* POI List */}
                  <div className="space-y-2 max-h-[200px] overflow-y-auto hide-scrollbar">
                    {filteredPois.map((poi) => (
                      <button
                        key={poi.id}
                        onClick={() => setSelectedPoi(poi)}
                        className={`w-full p-3 rounded-xl border-2 transition-all text-left flex items-center gap-3 ${
                          selectedPoi?.id === poi.id
                            ? 'border-primary bg-primary/5'
                            : 'border-border hover:border-muted-foreground/30'
                        }`}
                      >
                        <div className="w-9 h-9 rounded-lg bg-muted flex items-center justify-center">
                          <span className="material-icons-round text-muted-foreground text-lg">place</span>
                        </div>
                        <div>
                          <p className="font-semibold text-sm text-foreground">{poi.name}</p>
                          <p className="text-xs text-muted-foreground">{poi.category}</p>
                        </div>
                        {selectedPoi?.id === poi.id && (
                          <span className="material-icons-round text-primary ml-auto">check_circle</span>
                        )}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {missionType === 'PICKUP' && !selectedStore && (
                <div className="space-y-2 max-h-[300px] overflow-y-auto hide-scrollbar">
                  {availableStores.map((store) => (
                    <button
                      key={store.id}
                      onClick={() => setSelectedStore(store.id)}
                      className="w-full p-3 rounded-xl border border-border hover:border-muted-foreground/30 transition-all text-left flex items-center gap-3 active-press"
                    >
                      <div className="w-10 h-10 rounded-lg bg-muted flex items-center justify-center">
                        <span className="material-icons-round text-muted-foreground">{store.icon}</span>
                      </div>
                      <div>
                        <p className="font-semibold text-sm text-foreground">{store.name}</p>
                        <p className="text-xs text-muted-foreground">{store.location}</p>
                      </div>
                      <span className="material-icons-round text-muted-foreground ml-auto">chevron_right</span>
                    </button>
                  ))}
                </div>
              )}

              {missionType === 'PICKUP' && selectedStore && (
                <div className="space-y-3">
                  <button
                    onClick={() => { setSelectedStore(null); setSelectedItems([]); }}
                    className="flex items-center gap-1 text-primary text-sm font-medium"
                  >
                    <span className="material-icons-round text-sm">arrow_back</span>
                    Change store
                  </button>

                  <p className="text-sm font-medium text-muted-foreground">
                    {stores.find(s => s.id === selectedStore)?.name} — Select items
                  </p>

                  <div className="space-y-2 max-h-[200px] overflow-y-auto hide-scrollbar">
                    {storeProducts[selectedStore]?.map((product) => {
                      const inCart = selectedItems.find(i => i.name === product.name);
                      return (
                        <div key={product.name} className="flex items-center gap-3 p-3 rounded-xl border border-border">
                          <div className="flex-1">
                            <p className="text-sm font-medium text-foreground">{product.name}</p>
                            <p className="text-xs text-primary font-medium">${product.price.toFixed(2)}</p>
                          </div>
                          <div className="flex items-center gap-2">
                            {inCart && (
                              <span className="bg-primary text-primary-foreground px-2 py-0.5 rounded-full text-xs font-bold">
                                {inCart.quantity}
                              </span>
                            )}
                            <button
                              onClick={() => handleAddItem(product)}
                              className="w-8 h-8 rounded-full bg-primary text-primary-foreground flex items-center justify-center active-press-sm"
                            >
                              <span className="material-icons-round text-sm">add</span>
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              <button
                onClick={handleNext}
                disabled={!canProceedDetail}
                className="w-full bg-primary text-white py-4 rounded-2xl font-bold shadow-lg shadow-primary/30 hover:bg-primary/90 transition-colors active-press-sm disabled:opacity-50 flex items-center justify-center gap-2"
              >
                <span className="material-icons-round">arrow_forward</span>
                Review Mission
              </button>
            </>
          )}

          {/* Step 4: Mission Summary */}
          {wizardStep === 'mission-summary' && (
            <>
              {/* Summary Card */}
              <div className="bg-muted rounded-2xl p-4 space-y-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
                    <span className="material-icons-round text-primary">
                      {missionType === 'GUIDE' ? 'alt_route' : 'shopping_bag'}
                    </span>
                  </div>
                  <div>
                    <p className="font-bold text-foreground">
                      {missionType === 'GUIDE' ? 'Guide Mission' : 'Pickup Mission'}
                    </p>
                    <p className="text-xs text-muted-foreground">Task-based session</p>
                  </div>
                </div>

                {missionType === 'GUIDE' && selectedPoi && (
                  <div className="bg-card rounded-xl p-3 border border-border">
                    <p className="text-sm font-medium text-foreground">{selectedPoi.name}</p>
                    <p className="text-xs text-muted-foreground">{selectedPoi.category}</p>
                  </div>
                )}

                {missionType === 'PICKUP' && selectedStore && (
                  <div className="bg-card rounded-xl p-3 border border-border space-y-1">
                    <p className="text-sm font-semibold text-foreground">
                      {stores.find(s => s.id === selectedStore)?.name}
                    </p>
                    {selectedItems.map((item) => (
                      <div key={item.name} className="flex justify-between text-xs">
                        <span className="text-muted-foreground">{item.name} × {item.quantity}</span>
                        <span className="text-foreground font-medium">${(item.price * item.quantity).toFixed(2)}</span>
                      </div>
                    ))}
                    <div className="border-t border-border pt-1 flex justify-between text-sm">
                      <span className="font-medium text-foreground">Total</span>
                      <span className="font-bold text-foreground">
                        ${selectedItems.reduce((a, b) => a + b.price * b.quantity, 0).toFixed(2)}
                      </span>
                    </div>
                  </div>
                )}
              </div>

              {/* Notice */}
              <div className="bg-amber-50 dark:bg-amber-900/20 rounded-xl p-3 flex items-start gap-2">
                <span className="material-icons-round text-amber-500 text-lg mt-0.5">info</span>
                <p className="text-xs text-amber-800 dark:text-amber-300">
                  1건의 미션 완료 시 세션이 자동 종료됩니다
                </p>
              </div>

              {/* Find Robot */}
              <button
                onClick={handleStartTask}
                disabled={isLoading}
                className="w-full bg-primary text-white py-4 rounded-2xl font-bold shadow-lg shadow-primary/30 hover:bg-primary/90 transition-colors active-press-sm disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {isLoading ? (
                  <>
                    <span className="material-icons-round animate-spin">sync</span>
                    Finding your robot...
                  </>
                ) : (
                  <>
                    <span className="material-icons-round">smart_toy</span>
                    Find Robot
                  </>
                )}
              </button>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

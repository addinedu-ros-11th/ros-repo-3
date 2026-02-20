import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAppStore, PickupStatus } from '@/store/appStore';

const pickupSteps = [
  { status: 'MOVING', label: 'Robot Moving', icon: 'near_me' },
  { status: 'LOADING', label: 'Loading Items', icon: 'inventory_2' },
  { status: 'LOADED', label: 'Items Loaded', icon: 'check_circle' },
  { status: 'MEETUP_SET', label: 'Meet-up Set', icon: 'place' },
  { status: 'RETURNING', label: 'Returning', icon: 'directions' },
  { status: 'DONE', label: 'Complete', icon: 'celebration' },
];

export default function PickupMode() {
  const navigate = useNavigate();
  const { 
    stores, 
    storeProducts: storeProductsData,
    pickupOrder, 
    createPickupOrder, 
    setPickupStatus,
    setMeetupLocation,
    sessionState,
    session,
    taskMission,
    confirmSlotEmpty,
    completeTaskSession,
    lockboxSlots,
    openSlot,
    pois,
  } = useAppStore();

  const [searchParams] = useSearchParams();
  const preStore = searchParams.get('store');
  const preItem = searchParams.get('item');

  const [step, setStep] = useState<'store' | 'items' | 'confirm' | 'payment' | 'tracking'>(() => {
    // Resume tracking if there's an active pickup order (not IDLE and not DONE)
    if (pickupOrder && pickupOrder.status !== 'IDLE' && pickupOrder.status !== 'DONE') {
      return 'tracking';
    }
    if (preStore) return 'items';
    return 'store';
  });
  const [selectedStore, setSelectedStore] = useState<string | null>(preStore);
  const [selectedItems, setSelectedItems] = useState<{ name: string; quantity: number; price: number }[]>(() => {
    if (preStore && preItem) {
      const products = storeProductsData[preStore];
      const found = products?.find(p => p.name === preItem);
      if (found) return [{ name: found.name, quantity: 1, price: found.price }];
    }
    return [];
  });
  const [showLockboxRetrieval, setShowLockboxRetrieval] = useState(false);
  const [retrievalToken, setRetrievalToken] = useState<string | null>(null);
  const [paymentDone, setPaymentDone] = useState(false);
  const [showMeetupOverlay, setShowMeetupOverlay] = useState(false);

  const isActive = sessionState === 'ACTIVE';
  const isTaskMode = session.type === 'TASK';
  const hasEmptySlot = lockboxSlots.some(s => s.status === 'EMPTY');

  // Use shared store products data (just name + price for pickup)
  const storeProducts: Record<string, { name: string; price: number }[]> = Object.fromEntries(
    Object.entries(storeProductsData).map(([k, v]) => [k, v.map(p => ({ name: p.name, price: p.price }))])
  );

  const handleStoreSelect = (storeId: string) => {
    setSelectedStore(storeId);
    setStep('items');
  };

  const handleAddItem = (product: { name: string; price: number }) => {
    const existing = selectedItems.find(i => i.name === product.name);
    if (existing) {
      setSelectedItems(items => 
        items.map(i => i.name === product.name ? { ...i, quantity: i.quantity + 1 } : i)
      );
    } else {
      setSelectedItems(items => [...items, { ...product, quantity: 1 }]);
    }
  };

  const handleConfirmOrder = () => {
    if (selectedStore && selectedItems.length > 0) {
      setStep('payment');
    }
  };

  const handleMakePayment = () => {
    if (selectedStore) {
      createPickupOrder(selectedStore, selectedItems);
      setPickupStatus('MOVING');
      setStep('tracking');
    }
  };

  const handleSimulateProgress = () => {
    if (!pickupOrder) return;
    const statusOrder: PickupStatus[] = ['MOVING', 'LOADING', 'LOADED', 'MEETUP_SET', 'RETURNING', 'DONE'];
    const currentIndex = statusOrder.indexOf(pickupOrder.status);
    if (currentIndex < statusOrder.length - 1) {
      setPickupStatus(statusOrder[currentIndex + 1]);
    }
  };

  const getStepIndex = (status: PickupStatus) => {
    return pickupSteps.findIndex(s => s.status === status);
  };

  // Find which slot is used for this pickup (use first RESERVED or first EMPTY)
  const getPickupSlot = () => {
    const reserved = lockboxSlots.find(s => s.status === 'RESERVED');
    if (reserved) return reserved.slotNumber;
    const empty = lockboxSlots.find(s => s.status === 'EMPTY');
    return empty?.slotNumber || 4;
  };

  const handleOpenLockbox = () => {
    const slotNum = getPickupSlot();
    openSlot(slotNum);
    setRetrievalToken(`TKN-${Math.floor(1000 + Math.random() * 9000)}`);
  };

  const handleConfirmRetrieval = () => {
    const slotNum = getPickupSlot();
    confirmSlotEmpty(slotNum);
    completeTaskSession();
    navigate('/task-complete');
  };

  // Task mode: show lockbox retrieval after DONE
  // if (step === 'tracking' && pickupOrder?.status === 'DONE' && isTaskMode && !showLockboxRetrieval) {
  //   setShowLockboxRetrieval(true);
  // }
  useEffect(() => {
    if (step === 'tracking' && pickupOrder?.status === 'DONE' && isTaskMode && !showLockboxRetrieval) {
      setShowLockboxRetrieval(true);
    }
  }, [step, pickupOrder?.status, isTaskMode, showLockboxRetrieval]);

  if (step === 'tracking' && pickupOrder && showLockboxRetrieval && isTaskMode) {
    const slotNum = getPickupSlot();

    return (
      <div className="space-y-5">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Pickup Complete</h1>
          <p className="text-muted-foreground text-sm mt-1">Retrieve your items from the lockbox</p>
        </div>

        {/* Lockbox info card */}
        <div className="bg-gradient-to-br from-amber-400 to-orange-500 rounded-3xl p-6 relative overflow-hidden">
          <div className="card-decoration -right-10 -top-10 w-40 h-40 bg-white/20" />
          <div className="relative z-10">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 rounded-xl bg-white/20 flex items-center justify-center">
                <span className="material-icons-round text-white text-2xl">lock</span>
              </div>
              <div>
                <p className="text-white/70 text-xs font-medium">Lockbox</p>
                <h3 className="text-white font-bold text-lg">Slot {slotNum}</h3>
              </div>
            </div>

            <div className="bg-white/10 backdrop-blur-sm rounded-2xl p-4 mb-3">
              <p className="text-white text-sm font-medium">
                물건이 락박스 Slot {slotNum}에 보관되어 있습니다
              </p>
              <p className="text-white/60 text-xs mt-1">
                세션 종료 전에 모든 물건을 회수해 주세요
              </p>
            </div>

            {/* Order info */}
            <div className="bg-white/10 backdrop-blur-sm rounded-xl p-3 flex items-center gap-2">
              <span className="material-icons-round text-white/70">shopping_bag</span>
              <span className="text-white/90 text-sm font-medium">
                Order {pickupOrder.orderId} • {pickupOrder.storeName}
              </span>
            </div>
          </div>
        </div>

        {/* Token display */}
        {retrievalToken && (
          <div className="bg-card rounded-2xl p-5 border border-border text-center">
            <p className="text-xs font-medium text-muted-foreground mb-2">One-time Access Code</p>
            <p className="text-3xl font-mono font-bold text-primary tracking-widest">{retrievalToken}</p>
            <p className="text-xs text-muted-foreground mt-2">Show this code to open the lockbox</p>
          </div>
        )}

        {/* Open Lockbox button */}
        {!retrievalToken && (
          <button
            onClick={handleOpenLockbox}
            className="w-full py-4 rounded-2xl bg-card border border-border text-foreground font-bold active-press-sm flex items-center justify-center gap-2"
          >
            <span className="material-icons-round">lock_open</span>
            Open Lockbox
          </button>
        )}

        {/* Confirm retrieval */}
        <div className="fixed bottom-28 left-5 right-5 max-w-[430px] mx-auto">
          <button
            onClick={handleConfirmRetrieval}
            className="w-full py-4 rounded-2xl bg-primary text-primary-foreground font-bold shadow-lg shadow-primary/30 active-press-sm flex items-center justify-center gap-2"
          >
            <span className="material-icons-round">check</span>
            모든 물건을 회수했습니다
          </button>
        </div>
      </div>
    );
  }

  if (step === 'tracking' && pickupOrder) {
    const currentStep = getStepIndex(pickupOrder.status);
    const isMeetupSet = pickupOrder.status === 'MEETUP_SET';
    const isDone = pickupOrder.status === 'DONE';

    return (
      <div className="space-y-5">
        <div>
          <button onClick={() => navigate('/mode')} className="flex items-center gap-1 text-primary mb-2">
            <span className="material-icons-round text-sm">arrow_back</span>
            <span className="text-sm font-medium">Back to Modes</span>
          </button>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Order Tracking</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Order {pickupOrder.orderId} from {pickupOrder.storeName}
          </p>
        </div>

        {/* Progress Steps */}
        <div className="bg-card rounded-3xl p-6 border border-border">
          <div className="space-y-4">
            {pickupSteps.map((s, index) => (
              <div key={s.status} className="flex items-center gap-4">
                <div className={`w-10 h-10 rounded-full flex items-center justify-center transition-all ${
                  index <= currentStep 
                    ? 'bg-primary text-primary-foreground' 
                    : 'bg-muted text-muted-foreground'
                }`}>
                  <span className="material-icons-round text-lg">{s.icon}</span>
                </div>
                <div className="flex-1">
                  <p className={`font-medium ${
                    index <= currentStep ? 'text-foreground' : 'text-muted-foreground'
                  }`}>
                    {s.label}
                  </p>
                  {/* Show selected meetup location */}
                  {s.status === 'MEETUP_SET' && pickupOrder.meetupLocation && index <= currentStep && (
                    <p className="text-xs text-primary">{pickupOrder.meetupLocation}</p>
                  )}
                </div>
                {index === currentStep && (
                  <span className="w-2 h-2 bg-primary rounded-full animate-pulse" />
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Meet-up Location — Button to open overlay */}
        {isMeetupSet && !pickupOrder.meetupLocation && (
          <button
            onClick={() => setShowMeetupOverlay(true)}
            className="w-full py-4 rounded-2xl bg-primary text-primary-foreground font-bold shadow-lg shadow-primary/30 active-press-sm flex items-center justify-center gap-2"
          >
            <span className="material-icons-round">place</span>
            Choose Meet-up Point
          </button>
        )}

        {/* Meet-up Overlay */}
        {showMeetupOverlay && (
          <div className="fixed inset-0 z-50 flex items-end justify-center" onClick={() => setShowMeetupOverlay(false)}>
            <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" />
            <div
              className="relative w-full max-w-[430px] bg-card rounded-t-3xl p-6 pb-10 space-y-3 animate-in slide-in-from-bottom duration-200"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="w-10 h-1 bg-muted-foreground/30 rounded-full mx-auto mb-2" />
              <h3 className="font-bold text-foreground text-center">Choose a Meet-up Point</h3>
              <p className="text-xs text-muted-foreground text-center mb-2">Select where you'd like to meet the robot</p>
              <div className="space-y-2 max-h-72 overflow-y-auto">
                {pois.map((poi) => (
                  <button
                    key={poi.id}
                    onClick={() => {
                      setMeetupLocation(poi.name);
                      setPickupStatus('RETURNING');
                      setShowMeetupOverlay(false);
                    }}
                    className="w-full flex items-center gap-3 p-3 rounded-xl bg-muted/50 hover:bg-muted active:scale-[0.98] transition-all text-left"
                  >
                    <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center">
                      <span className="material-icons-round text-primary text-lg">place</span>
                    </div>
                    <div className="flex-1">
                      <p className="font-medium text-sm text-foreground">{poi.name}</p>
                      <p className="text-xs text-muted-foreground">{poi.category}</p>
                    </div>
                    <span className="material-icons-round text-muted-foreground text-lg">chevron_right</span>
                  </button>
                ))}
              </div>
              <button
                onClick={() => setShowMeetupOverlay(false)}
                className="w-full py-3 rounded-xl text-muted-foreground font-medium text-sm"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Demo Button */}
        {isDone ? (
          <button
            onClick={() => navigate('/mode')}
            className="w-full py-3 rounded-xl bg-primary text-primary-foreground font-medium active-press-sm flex items-center justify-center gap-2"
          >
            <span className="material-icons-round text-lg">check_circle</span>
            Back to Control Mode
          </button>
        ) : (
          <button
            onClick={handleSimulateProgress}
            disabled={isMeetupSet && !pickupOrder.meetupLocation}
            className="w-full py-3 rounded-xl bg-muted text-muted-foreground font-medium active-press-sm disabled:opacity-50"
          >
            Simulate Next Step (Demo)
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div>
        <button onClick={() => step === 'store' ? navigate('/mode') : setStep('store')} className="flex items-center gap-1 text-primary mb-2">
          <span className="material-icons-round text-sm">arrow_back</span>
          <span className="text-sm font-medium">{step === 'store' ? 'Back to Modes' : 'Back'}</span>
        </button>
        <h1 className="text-3xl font-bold tracking-tight text-foreground">Pickup Order</h1>
        <p className="text-muted-foreground text-sm mt-1">
          {step === 'store' && 'Select a store to order from'}
          {step === 'items' && 'Select items to pickup'}
           {step === 'confirm' && 'Review your order'}
           {step === 'payment' && 'Complete payment'}
         </p>
      </div>

      {/* No empty slot warning */}
      {step === 'store' && !hasEmptySlot && (
        <div className="bg-destructive/10 border border-destructive/30 rounded-2xl p-4 flex items-start gap-3">
          <span className="material-icons-round text-destructive mt-0.5">warning</span>
          <div>
            <p className="font-semibold text-destructive text-sm">No Empty Lockbox Available</p>
            <p className="text-xs text-destructive/80 mt-1">
              All lockbox slots are occupied. Please empty a slot before placing a pickup order.
            </p>
          </div>
        </div>
      )}

      {/* Store Selection */}
      {step === 'store' && (
        <div className="space-y-3">
          {stores.filter(s => s.open && storeProducts[s.id]).map((store) => (
            <button
              key={store.id}
              onClick={() => handleStoreSelect(store.id)}
              disabled={!hasEmptySlot}
              className="w-full bg-card rounded-2xl p-4 border border-border flex items-center gap-4 text-left active-press disabled:opacity-50 disabled:pointer-events-none"
            >
              <div className="w-12 h-12 rounded-xl bg-muted flex items-center justify-center">
                <span className="material-icons-round text-xl text-muted-foreground">{store.icon}</span>
              </div>
              <div className="flex-1">
                <h3 className="font-semibold text-foreground">{store.name}</h3>
                <p className="text-xs text-muted-foreground">{store.location}</p>
              </div>
              <span className="material-icons-round text-muted-foreground">chevron_right</span>
            </button>
          ))}
        </div>
      )}

      {/* Item Selection */}
      {step === 'items' && selectedStore && (
        <div className="space-y-3">
          {storeProducts[selectedStore]?.map((product) => {
            const inCart = selectedItems.find(i => i.name === product.name);
            return (
              <div 
                key={product.name}
                className="bg-card rounded-2xl p-4 border border-border flex items-center gap-4"
              >
                <div className="flex-1">
                  <h3 className="font-semibold text-foreground">{product.name}</h3>
                  <p className="text-sm text-primary font-medium">${product.price.toFixed(2)}</p>
                </div>
                <div className="flex items-center gap-2">
                  {inCart && (
                    <span className="bg-primary text-primary-foreground px-2 py-0.5 rounded-full text-sm font-bold">
                      {inCart.quantity}
                    </span>
                  )}
                  <button
                    onClick={() => handleAddItem(product)}
                    className="w-10 h-10 rounded-full bg-primary text-primary-foreground flex items-center justify-center active-press-sm"
                  >
                    <span className="material-icons-round">add</span>
                  </button>
                </div>
              </div>
            );
          })}

          {selectedItems.length > 0 && (
            <div className="fixed bottom-28 left-5 right-5 max-w-[430px] mx-auto">
              <button
                onClick={() => setStep('confirm')}
                className="w-full py-4 rounded-2xl bg-primary text-primary-foreground font-bold shadow-lg shadow-primary/30 active-press-sm flex items-center justify-center gap-2"
              >
                Continue ({selectedItems.reduce((a, b) => a + b.quantity, 0)} items)
              </button>
            </div>
          )}
        </div>
      )}

      {/* Confirm */}
      {step === 'confirm' && (
        <div className="space-y-4">
          <div className="bg-card rounded-2xl p-4 border border-border divide-y divide-border">
            {selectedItems.map((item) => (
              <div key={item.name} className="py-3 flex justify-between first:pt-0 last:pb-0">
                <div>
                  <p className="font-medium text-foreground">{item.name}</p>
                  <p className="text-xs text-muted-foreground">Qty: {item.quantity}</p>
                </div>
                <p className="font-semibold text-foreground">
                  ${(item.price * item.quantity).toFixed(2)}
                </p>
              </div>
            ))}
          </div>

          <div className="bg-muted rounded-2xl p-4">
            <div className="flex justify-between">
              <span className="font-medium text-muted-foreground">Total</span>
              <span className="text-xl font-bold text-foreground">
                ${selectedItems.reduce((a, b) => a + b.price * b.quantity, 0).toFixed(2)}
              </span>
            </div>
          </div>

          <button
            onClick={handleConfirmOrder}
            disabled={!isActive}
            className="w-full py-4 rounded-2xl bg-primary text-primary-foreground font-bold shadow-lg shadow-primary/30 active-press-sm disabled:opacity-50 flex items-center justify-center gap-2"
          >
            <span className="material-icons-round">shopping_bag</span>
            Confirm Order
          </button>
        </div>
       )}

      {/* Tap to Pay */}
      {step === 'payment' && (
        <div className="space-y-6">
          <div className="bg-card rounded-2xl p-4 border border-border divide-y divide-border">
            {selectedItems.map((item) => (
              <div key={item.name} className="py-3 flex justify-between first:pt-0 last:pb-0">
                <div>
                  <p className="font-medium text-foreground">{item.name}</p>
                  <p className="text-xs text-muted-foreground">Qty: {item.quantity}</p>
                </div>
                <p className="font-semibold text-foreground">
                  ${(item.price * item.quantity).toFixed(2)}
                </p>
              </div>
            ))}
            <div className="pt-3 flex justify-between">
              <span className="font-medium text-muted-foreground">Total</span>
              <span className="text-lg font-bold text-foreground">
                ${selectedItems.reduce((a, b) => a + b.price * b.quantity, 0).toFixed(2)}
              </span>
            </div>
          </div>

          <button
            onClick={handleMakePayment}
            className="w-full py-4 rounded-2xl bg-primary text-primary-foreground font-bold shadow-lg shadow-primary/30 active-press-sm flex items-center justify-center gap-2"
          >
            <span className="material-icons-round">payment</span>
            Make Payment
          </button>
        </div>
      )}
    </div>
  );
}
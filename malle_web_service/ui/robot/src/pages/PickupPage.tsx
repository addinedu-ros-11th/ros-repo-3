import { useRobotStore } from '@/stores/robotStore';
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { stores, getProductsByStore } from '@/data/stores';
import type { OrderItem, PickupStatus } from '@/types/robot';

export function PickupPage() {
  const { pickup, createPickupOrder, setShowLoadingOverlay, lockboxSlots, pendingPickupStore, setPendingPickupStore } = useRobotStore();
  const navigate = useNavigate();
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [selectedStore, setSelectedStore] = useState<string | null>(null);
  const [cart, setCart] = useState<OrderItem[]>([]);

  // Check for pending pickup store from voice command
  useEffect(() => {
    if (pendingPickupStore) {
      handleStoreSelect(pendingPickupStore);
      setPendingPickupStore(null);
    }
  }, [pendingPickupStore]);

  const hasEmptySlot = lockboxSlots.some(s => s.status === 'EMPTY');
  const products = selectedStore ? getProductsByStore(selectedStore) : [];

  const handleStoreSelect = (storeId: string) => {
    setSelectedStore(storeId);
    setCart([]);
    setStep(2);
  };

  const handleAddProduct = (product: typeof products[0]) => {
    setCart(prev => {
      const existing = prev.find(item => item.name === product.name);
      if (existing) {
        return prev.map(item => item.name === product.name ? { ...item, quantity: item.quantity + 1 } : item);
      }
      return [...prev, { name: product.name, quantity: 1, price: product.price }];
    });
  };

  const handleRemoveProduct = (productName: string) => {
    setCart(prev => {
      const existing = prev.find(item => item.name === productName);
      if (existing && existing.quantity > 1) {
        return prev.map(item => item.name === productName ? { ...item, quantity: item.quantity - 1 } : item);
      }
      return prev.filter(item => item.name !== productName);
    });
  };

  const handleProceedToPayment = () => {
    setStep(3);
  };

  const handlePayment = () => {
    const store = stores.find(s => s.id === selectedStore);
    if (!store) return;

    createPickupOrder({
      orderId: `#${Math.floor(Math.random() * 9000) + 1000}`,
      storeName: store.name,
      items: cart,
      slotId: 0, // Will be assigned by createPickupOrder
      meetupLocation: null,
    });

    setShowLoadingOverlay(true);
    setStep(1);
    setSelectedStore(null);
    setCart([]);
  };

  const totalPrice = cart.reduce((sum, item) => sum + item.price * item.quantity, 0);
  const totalItems = cart.reduce((sum, item) => sum + item.quantity, 0);

  const getStatusSteps = (status: PickupStatus) => {
    const allSteps = [
      { id: 'moving', label: 'Moving to pickup', icon: 'directions' },
      { id: 'arrived', label: 'Arrived at store', icon: 'place' },
      { id: 'loading', label: 'Loading items', icon: 'inventory_2' },
      { id: 'loaded', label: 'Loaded - heading to meet-up', icon: 'local_shipping' },
      { id: 'meetup', label: 'Arrived at meet-up', icon: 'flag' },
      { id: 'done', label: 'Complete', icon: 'check_circle' },
    ];

    const statusMap: Record<PickupStatus, number> = {
      'MOVING': 0,
      'ARRIVED': 1,
      'STAFF_PIN': 2,
      'LOADING': 2,
      'LOADED': 3,
      'MEETUP_SET': 4,
      'RETURNING': 4,
      'DONE': 5,
    };

    return allSteps.map((step, index) => ({
      ...step,
      completed: index < statusMap[status],
      current: index === statusMap[status],
    }));
  };

  // If there's an active pickup order, show status
  if (pickup.currentOrder) {
    const steps = getStatusSteps(pickup.currentOrder.status);

    return (
      <div>
        <h1 className="text-page-title mb-8">Pickup Status</h1>

        <div className="max-w-2xl mx-auto">
          <div className="robot-card-pink mb-6">
            <div className="absolute -right-10 -top-10 w-48 h-48 bg-white/15 rounded-full blur-3xl" />
            <div className="relative z-10">
              <div className="flex items-center justify-between mb-4">
                <span className="bg-white/20 px-3 py-1 rounded-full text-xs font-bold text-white">
                  {pickup.currentOrder.orderId}
                </span>
                <span className="text-white/80">{pickup.currentOrder.storeName}</span>
              </div>
              <div className="flex items-center space-x-3">
                <span className="material-icons-round text-white text-3xl">shopping_bag</span>
                <div>
                  <p className="text-xl font-bold text-white">Slot {pickup.currentOrder.slotId}</p>
                  <p className="text-white/70">{pickup.currentOrder.items.length} items</p>
                </div>
              </div>
            </div>
          </div>

          {/* Status Timeline */}
          <div className="robot-card-white">
            <h3 className="text-lg font-bold text-foreground mb-6">Progress</h3>
            <div className="space-y-4">
              {steps.map((step, index) => (
                <div key={step.id} className="flex items-start space-x-4">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${
                    step.completed
                      ? 'bg-emerald-500 text-white'
                      : step.current
                      ? 'bg-primary text-white ring-4 ring-primary/30'
                      : 'bg-slate-200 dark:bg-slate-700 text-slate-400'
                  }`}>
                    <span className="material-icons-round text-lg">
                      {step.completed ? 'check' : step.icon}
                    </span>
                  </div>
                  <div className={`flex-1 pb-4 ${index < steps.length - 1 ? 'border-l-2 border-slate-200 dark:border-slate-700 ml-5 pl-8 -mt-2' : ''}`}>
                    <p className={`font-semibold ${step.current ? 'text-foreground' : step.completed ? 'text-muted-foreground' : 'text-slate-400'}`}>
                      {step.label}
                    </p>
                    {step.current && (
                      <p className="text-sm text-primary animate-pulse">In progress...</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Order Creation Flow
  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center space-x-3">
          {step === 1 && (
            <button onClick={() => navigate('/mode')} className="btn-ghost p-2">
              <span className="material-icons-round">arrow_back</span>
            </button>
          )}
          {step > 1 && (
            <button onClick={() => setStep(s => (s - 1) as 1 | 2)} className="btn-ghost p-2">
              <span className="material-icons-round">arrow_back</span>
            </button>
          )}
          <h1 className="text-page-title">Create Pickup Order</h1>
        </div>
      </div>

      {!hasEmptySlot && (
        <div className="bg-amber-100 dark:bg-amber-900/30 border border-amber-300 dark:border-amber-700 rounded-2xl p-4 mb-6">
          <div className="flex items-center space-x-3">
            <span className="material-icons-round text-amber-600">warning</span>
            <p className="text-amber-700 dark:text-amber-300 font-medium">No empty lockbox slots available</p>
          </div>
        </div>
      )}

      {/* Step Indicator */}
      <div className="flex items-center justify-center mb-8">
        {[1, 2, 3].map((s) => (
          <div key={s} className="flex items-center">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm ${
              step >= s ? 'bg-primary text-white' : 'bg-slate-200 dark:bg-slate-700 text-slate-400'
            }`}>
              {s}
            </div>
            {s < 3 && (
              <div className={`w-16 h-1 mx-2 ${step > s ? 'bg-primary' : 'bg-slate-200 dark:bg-slate-700'}`} />
            )}
          </div>
        ))}
      </div>

      {/* Step 1: Select Store */}
      {step === 1 && (
        <div className="grid grid-cols-3 gap-4">
          {stores.filter(s => s.open).map((store) => (
            <button
              key={store.id}
              onClick={() => handleStoreSelect(store.id)}
              disabled={!hasEmptySlot}
              className="robot-card-white text-left hover:border-primary disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <div className="flex items-center space-x-3">
                <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
                  <span className="material-icons-round text-primary">{store.icon}</span>
                </div>
                <div>
                  <p className="font-semibold text-foreground">{store.name}</p>
                  <p className="text-sm text-muted-foreground">{store.category}</p>
                </div>
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Step 2: Select Products */}
      {step === 2 && selectedStore && (
        <div className="grid grid-cols-2 gap-6">
          <div className="robot-card-white">
            <h3 className="text-lg font-bold text-foreground mb-4">Products</h3>
            <div className="space-y-3">
              {products.map((product) => {
                const inCart = cart.find(item => item.name === product.name);
                return (
                  <div key={product.id} className="flex items-center justify-between p-3 rounded-xl border border-slate-200 dark:border-slate-700">
                    <div>
                      <p className="font-semibold text-foreground">{product.name}</p>
                      <p className="text-sm text-primary font-medium">${product.price.toFixed(2)}</p>
                    </div>
                    <div className="flex items-center space-x-2">
                      {inCart && (
                        <>
                          <button onClick={() => handleRemoveProduct(product.name)} className="w-8 h-8 rounded-lg bg-slate-100 dark:bg-slate-800 flex items-center justify-center">
                            <span className="material-icons-round text-sm">remove</span>
                          </button>
                          <span className="w-8 text-center font-bold">{inCart.quantity}</span>
                        </>
                      )}
                      <button onClick={() => handleAddProduct(product)} className="w-8 h-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center">
                        <span className="material-icons-round text-sm">add</span>
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="robot-card-white">
            <h3 className="text-lg font-bold text-foreground mb-4">Cart</h3>
            {cart.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <span className="material-icons-round text-4xl mb-2">shopping_cart</span>
                <p>Cart is empty</p>
              </div>
            ) : (
              <>
                <div className="space-y-3 mb-4">
                  {cart.map((item) => (
                    <div key={item.name} className="flex items-center justify-between">
                      <span className="text-foreground">{item.name} × {item.quantity}</span>
                      <span className="font-medium text-foreground">${(item.price * item.quantity).toFixed(2)}</span>
                    </div>
                  ))}
                </div>
                <div className="border-t border-slate-200 dark:border-slate-700 pt-4 mb-6">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-foreground">Total ({totalItems} items)</span>
                    <span className="text-xl font-bold text-primary">${totalPrice.toFixed(2)}</span>
                  </div>
                </div>
                <button onClick={handleProceedToPayment} className="w-full btn-primary">
                  Proceed to Payment
                </button>
              </>
            )}
          </div>
        </div>
      )}

      {/* Step 3: Payment */}
      {step === 3 && (
        <div className="max-w-md mx-auto">
          <div className="robot-card-white text-center py-8">
            <span className="material-icons-round text-6xl text-primary mb-4 block">credit_card</span>
            <h3 className="text-xl font-bold text-foreground mb-2">Payment</h3>
            <p className="text-muted-foreground mb-6">Total: ${totalPrice.toFixed(2)}</p>
            
            <button onClick={handlePayment} className="btn-primary w-full mb-4">
              <span className="material-icons-round mr-2 align-middle">touch_app</span>
              Tap to Pay
            </button>
            <p className="text-xs text-muted-foreground">Demo: Click to simulate payment</p>
          </div>
        </div>
      )}
    </div>
  );
}

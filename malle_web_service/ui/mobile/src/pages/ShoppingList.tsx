import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppStore } from '@/store/appStore';
import { toast } from 'sonner';

export default function ShoppingList() {
  const navigate = useNavigate();
  const { shoppingList, toggleProductComplete, removeFromShoppingList, addToShoppingList, stores, storeProducts, addToGuideQueue, pois, sessionState } = useAppStore();
  const [showAddForm, setShowAddForm] = useState(false);
  const [addStep, setAddStep] = useState<'store' | 'product'>('store');
  const [selectedStoreId, setSelectedStoreId] = useState<string | null>(null);

  // Action sheet state
  const [actionItem, setActionItem] = useState<{ id: string; storeId: string; name: string } | null>(null);

  const isActive = sessionState === 'ACTIVE';

  // Group products by store
  const groupedProducts = shoppingList.reduce((acc, product) => {
    if (!acc[product.storeId]) {
      acc[product.storeId] = [];
    }
    acc[product.storeId].push(product);
    return acc;
  }, {} as Record<string, typeof shoppingList>);

  const pendingCount = shoppingList.filter(p => !p.completed).length;
  const storeCount = Object.keys(groupedProducts).length;

  const handleOptimizeRoute = () => {
    const storesToAdd: typeof pois = [];
    
    Object.keys(groupedProducts).forEach(storeId => {
      const hasIncomplete = groupedProducts[storeId].some(p => !p.completed);
      if (hasIncomplete) {
        // storeId (string)를 number로 변환하여 stores 찾기
        const store = stores.find(s => s.slug === storeId || String(s.id) === storeId);
        if (store && store.poi_id) {
          // store.poi_id로 pois 찾기
          const poi = pois.find(p => p.id === store.poi_id);
          if (poi) {
            storesToAdd.push(poi);
            addToGuideQueue(poi);
          }
        }
      }
    });
    
    if (storesToAdd.length > 0) {
      toast.success(`${storesToAdd.length}개 스토어를 Guide queue에 추가했습니다`);
      navigate('/mode/guide');
    } else {
      toast.error('추가할 미완료 항목이 없습니다');
    }
  };

  const handleSelectStore = (storeId: string) => {
    setSelectedStoreId(storeId);
    setAddStep('product');
  };

  const handleSelectProduct = (product: { name: string; option: string; price: number }) => {
    if (!selectedStoreId) return;
    addToShoppingList({
      storeId: selectedStoreId,
      name: product.name,
      option: product.option,
      price: product.price,
    });
    toast.success(`${product.name} added`);
    setShowAddForm(false);
    setAddStep('store');
    setSelectedStoreId(null);
  };

  const handleDelete = (id: string, name: string) => {
    removeFromShoppingList(id);
    toast.success(`${name} removed`);
  };

  const handleItemClick = (product: typeof shoppingList[0]) => {
    if (product.completed) return;
    setActionItem({ id: product.id, storeId: product.storeId, name: product.name });
  };

  const handleGuideAction = () => {
    if (!actionItem) return;
    const store = stores.find(s => s.slug === actionItem.storeId || String(s.id) === actionItem.storeId);
    const poi = store ? pois.find(p => p.id === store.poi_id) : undefined;
    if (poi) {
      addToGuideQueue(poi);
      toast.success(`${poi.name} added to Guide queue`);
      navigate('/mode/guide');
    }
    setActionItem(null);
  };

  const handlePickupAction = () => {
    if (!actionItem) return;
    navigate(`/mode/pickup?store=${encodeURIComponent(actionItem.storeId)}&item=${encodeURIComponent(actionItem.name)}`);
    setActionItem(null);
  };

  const closeAddForm = () => {
    setShowAddForm(false);
    setAddStep('store');
    setSelectedStoreId(null);
  };

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Shopping List</h1>
          <p className="text-muted-foreground text-sm mt-1">
            {pendingCount} items pending across {storeCount} stores
          </p>
        </div>
        <button
          onClick={() => showAddForm ? closeAddForm() : setShowAddForm(true)}
          className="p-2 rounded-xl bg-primary text-primary-foreground active-press-sm"
        >
          <span className="material-icons-round">{showAddForm ? 'close' : 'add'}</span>
        </button>
      </div>

      {/* Add Item — Store Selection */}
      {showAddForm && addStep === 'store' && (
        <div className="bg-card rounded-2xl border border-border p-4 space-y-3">
          <h3 className="font-semibold text-foreground text-sm">Select Store</h3>
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {stores.filter(s => storeProducts[s.id]).map(store => (
              <button
                key={store.id}
                onClick={() => handleSelectStore(store.id)}
                className="w-full flex items-center gap-3 p-3 rounded-xl bg-muted/50 hover:bg-muted active:scale-[0.98] transition-all text-left"
              >
                <div className="w-9 h-9 rounded-lg bg-foreground/10 flex items-center justify-center">
                  <span className="material-icons-round text-foreground text-lg">{store.icon}</span>
                </div>
                <div className="flex-1">
                  <p className="font-medium text-sm text-foreground">{store.name}</p>
                  <p className="text-xs text-muted-foreground">{store.category}</p>
                </div>
                <span className="material-icons-round text-muted-foreground">chevron_right</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Add Item — Product Selection */}
      {showAddForm && addStep === 'product' && selectedStoreId && (
        <div className="bg-card rounded-2xl border border-border p-4 space-y-3">
          <div className="flex items-center gap-2">
            <button onClick={() => setAddStep('store')} className="p-1">
              <span className="material-icons-round text-muted-foreground text-lg">arrow_back</span>
            </button>
            <h3 className="font-semibold text-foreground text-sm">
              {stores.find(s => s.id === selectedStoreId)?.name} — Select Product
            </h3>
          </div>
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {storeProducts[selectedStoreId]?.map((product) => {
              const alreadyAdded = shoppingList.some(p => p.storeId === selectedStoreId && p.name === product.name);
              return (
                <button
                  key={product.name}
                  onClick={() => !alreadyAdded && handleSelectProduct(product)}
                  disabled={alreadyAdded}
                  className={`w-full flex items-center gap-3 p-3 rounded-xl text-left transition-all ${
                    alreadyAdded 
                      ? 'bg-muted/30 opacity-50 cursor-not-allowed' 
                      : 'bg-muted/50 hover:bg-muted active:scale-[0.98]'
                  }`}
                >
                  <div className="flex-1">
                    <p className="font-medium text-sm text-foreground">{product.name}</p>
                    <p className="text-xs text-muted-foreground">{product.option}</p>
                  </div>
                  <span className="font-semibold text-sm text-foreground">${product.price.toFixed(2)}</span>
                  {alreadyAdded && (
                    <span className="material-icons-round text-primary text-lg">check_circle</span>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Store Groups */}
      <div className="space-y-4">
        {Object.entries(groupedProducts).map(([storeId, products]) => {
          const store = stores.find(s => s.slug === storeId || s.id === storeId);
          if (!store) return null;

          const completedCount = products.filter(p => p.completed).length;

          return (
            <div key={storeId} className="bg-card rounded-2xl shadow-sm border border-border overflow-hidden">
              {/* Store Header */}
              <div className="px-5 py-4 border-b border-border bg-muted/30 flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-foreground text-background flex items-center justify-center font-bold text-sm">
                  {store.name.charAt(0)}
                </div>
                <div className="flex-1">
                  <h3 className="font-bold text-foreground">{store.name}</h3>
                </div>
                <span className="text-xs bg-muted px-2 py-1 rounded-md text-muted-foreground font-medium">
                  {completedCount}/{products.length}
                </span>
              </div>

              {/* Products */}
              <div className="divide-y divide-border">
                {products.map((product) => (
                  <div 
                    key={product.id} 
                    className="px-5 py-4 flex items-center gap-4"
                  >
                    <button
                      onClick={() => toggleProductComplete(product.id)}
                      className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-all shrink-0 ${
                        product.completed
                          ? 'bg-primary border-primary'
                          : 'border-muted-foreground/30 hover:border-primary'
                      }`}
                    >
                      {product.completed && (
                        <span className="material-icons-round text-primary-foreground text-sm">check</span>
                      )}
                    </button>
                    <button
                      onClick={() => handleItemClick(product)}
                      className={`flex-1 min-w-0 text-left ${!product.completed && isActive ? 'cursor-pointer' : ''}`}
                      disabled={product.completed || !isActive}
                    >
                      <p className={`text-sm font-medium ${
                        product.completed ? 'line-through text-muted-foreground' : 'text-foreground'
                      }`}>
                        {product.name}
                      </p>
                      <p className="text-xs text-muted-foreground">{product.option}</p>
                    </button>
                    <p className={`font-semibold shrink-0 ${
                      product.completed ? 'text-muted-foreground' : 'text-foreground'
                    }`}>
                      ${product.price.toFixed(2)}
                    </p>
                    <button
                      onClick={() => handleDelete(product.id, product.name)}
                      className="p-1 rounded-lg text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors shrink-0"
                    >
                      <span className="material-icons-round text-lg">delete_outline</span>
                    </button>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {/* Action Sheet */}
      {actionItem && (
        <div className="fixed inset-0 z-50 flex items-end justify-center" onClick={() => setActionItem(null)}>
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" />
          <div 
            className="relative w-full max-w-[430px] bg-card rounded-t-3xl p-6 pb-10 space-y-3 animate-in slide-in-from-bottom duration-200"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="w-10 h-1 bg-muted-foreground/30 rounded-full mx-auto mb-2" />
            <h3 className="font-bold text-foreground text-center">{actionItem.name}</h3>
            <p className="text-xs text-muted-foreground text-center mb-2">
              {stores.find(s => s.slug === actionItem.storeId || s.id === actionItem.storeId)?.name}
            </p>

            <button
              onClick={handleGuideAction}
              className="w-full flex items-center gap-4 p-4 rounded-2xl bg-muted/50 hover:bg-muted active:scale-[0.98] transition-all"
            >
              <div className="w-11 h-11 rounded-xl bg-primary/10 flex items-center justify-center">
                <span className="material-icons-round text-primary text-xl">alt_route</span>
              </div>
              <div className="text-left flex-1">
                <p className="font-semibold text-foreground">Guide Me There</p>
                <p className="text-xs text-muted-foreground">Add store to Guide queue</p>
              </div>
              <span className="material-icons-round text-muted-foreground">chevron_right</span>
            </button>

            <button
              onClick={handlePickupAction}
              className="w-full flex items-center gap-4 p-4 rounded-2xl bg-muted/50 hover:bg-muted active:scale-[0.98] transition-all"
            >
              <div className="w-11 h-11 rounded-xl bg-accent/50 flex items-center justify-center">
                <span className="material-icons-round text-accent-foreground text-xl">shopping_bag</span>
              </div>
              <div className="text-left flex-1">
                <p className="font-semibold text-foreground">Pickup Order</p>
                <p className="text-xs text-muted-foreground">Robot picks up this item</p>
              </div>
              <span className="material-icons-round text-muted-foreground">chevron_right</span>
            </button>

            <button
              onClick={() => setActionItem(null)}
              className="w-full py-3 rounded-xl text-muted-foreground font-medium text-sm"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Route Optimizer Card */}
      {pendingCount > 0 && (
        <div className="bg-card-lime dark:bg-lime-900/60 rounded-3xl p-5 ring-1 ring-lime-900/5 shadow-lg relative overflow-hidden">
          <div className="card-decoration -right-10 -top-10 w-40 h-40 bg-white/40" />

          <div className="relative z-10">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-bold text-lime-950 dark:text-lime-50">Route Optimizer</h3>
              <span className="bg-lime-950/10 dark:bg-lime-100/20 text-lime-900 dark:text-lime-100 text-xs font-bold px-2.5 py-1 rounded-full">
                Efficient Path
              </span>
            </div>

            {/* Mini Map Preview */}
            <div className="h-32 bg-white/60 dark:bg-white/10 rounded-xl border border-lime-900/10 mb-4 map-pattern relative overflow-hidden">
              <svg className="absolute inset-0 w-full h-full" viewBox="0 0 200 100">
                <path
                  d="M 30 70 Q 60 30 100 50 T 170 30"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeDasharray="6 4"
                  className="text-lime-900/50 dark:text-lime-100/50"
                />
              </svg>
              <div className="absolute left-[15%] top-[70%] w-3 h-3 rounded-full bg-primary ring-4 ring-white" />
              <div className="absolute left-[50%] top-[50%] w-3 h-3 rounded-full bg-purple-500 ring-4 ring-white" />
              <div className="absolute left-[85%] top-[30%] w-3 h-3 rounded-full bg-foreground ring-4 ring-white" />
              <div className="absolute left-[25%] top-[60%]">
                <span className="material-icons-round text-primary text-lg">smart_toy</span>
              </div>
            </div>

            <p className="text-sm text-lime-900 dark:text-lime-100 mb-4">
              We found a route that saves you <strong>12 mins</strong> of walking.
            </p>

            <button
              onClick={handleOptimizeRoute}
              className="w-full bg-lime-950 dark:bg-lime-100 text-white dark:text-lime-950 rounded-xl py-3 font-semibold shadow-lg flex items-center justify-center gap-2 active-press-sm"
            >
              <span className="material-icons-round">alt_route</span>
              Suggest Optimal Route
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
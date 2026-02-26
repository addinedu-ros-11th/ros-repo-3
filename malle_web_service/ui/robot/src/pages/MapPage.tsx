import { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useRobotStore } from '@/stores/robotStore';
import { stores } from '@/data/stores';
import { toast } from 'sonner';

export function MapPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [highlightedStore, setHighlightedStore] = useState<string | null>(null);
  const [hoveredStore, setHoveredStore] = useState<string | null>(null);
  const [hoverTimeout, setHoverTimeout] = useState<ReturnType<typeof setTimeout> | null>(null);
  const { robot, addToGuideQueue, createPickupOrder, lockboxSlots, setPendingPickupStore } = useRobotStore();
  const navigate = useNavigate();

  useEffect(() => {
    const highlight = searchParams.get('highlight');
    if (highlight) {
      setHighlightedStore(highlight);
      searchParams.delete('highlight');
      setSearchParams(searchParams, { replace: true });
      const timer = setTimeout(() => setHighlightedStore(null), 3000);
      return () => clearTimeout(timer);
    }
  }, []);

  const hasEmptySlot = lockboxSlots.some(s => s.status === 'EMPTY');

  const handleAddToGuide = (store: typeof stores[0]) => {
    addToGuideQueue({
      poiId: store.id,
      poiName: store.name,
      floor: store.location,
      estimatedTime: Math.floor(Math.random() * 5) + 2,
    });
    toast.success(`Added ${store.name} to Guide Queue`, { duration: 2000 });
  };

  const handleOrderPickup = (store: typeof stores[0]) => {
    setPendingPickupStore(store.id);
    navigate('/mode/pickup');
  };

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-page-title">Mall Map</h1>
        <div className="flex items-center space-x-2">
          <button className="p-2 rounded-xl bg-card border border-slate-200 dark:border-slate-700">
            <span className="material-icons-round">add</span>
          </button>
          <button className="p-2 rounded-xl bg-card border border-slate-200 dark:border-slate-700">
            <span className="material-icons-round">remove</span>
          </button>
          <button className="p-2 rounded-xl bg-primary text-white">
            <span className="material-icons-round">my_location</span>
          </button>
        </div>
      </div>

      <div className="flex-1 relative bg-slate-100 dark:bg-slate-800 rounded-3xl overflow-visible map-grid">
        {/* Robot Position */}
        <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-10">
          <div className="relative">
            <div className="w-12 h-12 rounded-full bg-primary flex items-center justify-center shadow-lg">
              <span className="material-icons-round text-white">smart_toy</span>
            </div>
            <div className="absolute inset-0 rounded-full bg-primary/30 animate-ping" />
          </div>
        </div>

        {/* POI Markers */}
        {stores.slice(0, 6).map((store, index) => {
          const positions = [
            { x: '20%', y: '25%' },
            { x: '75%', y: '20%' },
            { x: '30%', y: '70%' },
            { x: '80%', y: '65%' },
            { x: '15%', y: '45%' },
            { x: '65%', y: '45%' },
          ];
          const pos = positions[index];
          
          return (
            <div
              key={store.id}
              className="absolute transform -translate-x-1/2 -translate-y-1/2 cursor-pointer"
              style={{ left: pos.x, top: pos.y }}
              onMouseEnter={() => {
                if (hoverTimeout) clearTimeout(hoverTimeout);
                setHoveredStore(store.id);
              }}
              onMouseLeave={() => {
                const t = setTimeout(() => setHoveredStore(null), 400);
                setHoverTimeout(t);
              }}
            >
              <div className={`w-10 h-10 rounded-full flex items-center justify-center shadow-md transition-all duration-300 ${
                highlightedStore === store.id
                  ? 'bg-primary ring-4 ring-primary/40 scale-125'
                  : store.open ? 'bg-card' : 'bg-slate-300'
              }`}>
                <span className={`material-icons-round ${
                  highlightedStore === store.id ? 'text-white' : store.open ? 'text-primary' : 'text-slate-500'
                }`}>{store.icon}</span>
              </div>
              {highlightedStore === store.id && (
                <div className="absolute inset-0 w-10 h-10 rounded-full bg-primary/30 animate-ping" />
              )}
              <span className={`absolute -bottom-6 left-1/2 -translate-x-1/2 whitespace-nowrap text-xs font-semibold px-2 py-1 rounded-lg shadow-sm transition-all duration-300 ${
                highlightedStore === store.id ? 'bg-primary text-white scale-110' : 'bg-card'
              }`}>
                {store.name}
              </span>

              {/* Popup on Hover */}
              <div className={`absolute bottom-full left-1/2 -translate-x-1/2 mb-2 transition-opacity z-[60] ${
                hoveredStore === store.id ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'
              }`}>
                <div className="bg-card rounded-2xl p-4 shadow-xl border border-slate-200 dark:border-slate-700 w-56">
                  <div className="flex items-center space-x-3 mb-3">
                    <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${store.open ? 'bg-primary/10' : 'bg-slate-100 dark:bg-slate-800'}`}>
                      <span className={`material-icons-round ${store.open ? 'text-primary' : 'text-slate-400'}`}>{store.icon}</span>
                    </div>
                    <div>
                      <p className="font-semibold text-foreground">{store.name}</p>
                      <p className="text-xs text-muted-foreground">{store.category}</p>
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground mb-3">{store.location}</p>
                  <div className="flex items-center space-x-2 mb-3">
                    <span className={`w-2 h-2 rounded-full ${store.open ? 'bg-emerald-500' : 'bg-red-500'}`} />
                    <span className="text-xs font-medium">{store.open ? 'Open' : 'Closed'}</span>
                  </div>
                  {store.open && (
                    <div className="flex space-x-2">
                      <button
                        onClick={() => handleAddToGuide(store)}
                        className="flex-1 btn-secondary text-xs py-2"
                      >
                        <span className="material-icons-round text-sm mr-1">alt_route</span>
                        Guide
                      </button>
                      {hasEmptySlot && (
                        <button
                          onClick={() => handleOrderPickup(store)}
                          className="flex-1 btn-primary text-xs py-2"
                        >
                          <span className="material-icons-round text-sm mr-1">shopping_bag</span>
                          Pickup
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}

        {/* Legend */}
        <div className="absolute bottom-4 left-4 bg-card/90 backdrop-blur-sm rounded-2xl p-4 shadow-lg border border-slate-200 dark:border-slate-700">
          <p className="text-xs font-bold text-muted-foreground mb-2 uppercase tracking-wide">Legend</p>
          <div className="space-y-2">
            <div className="flex items-center space-x-2">
              <div className="w-6 h-6 rounded-full bg-primary flex items-center justify-center">
                <span className="material-icons-round text-white text-xs">smart_toy</span>
              </div>
              <span className="text-xs text-foreground">Robot</span>
            </div>
            <div className="flex items-center space-x-2">
              <div className="w-6 h-6 rounded-full bg-card border border-primary flex items-center justify-center">
                <span className="material-icons-round text-primary text-xs">store</span>
              </div>
              <span className="text-xs text-foreground">Store (Open)</span>
            </div>
            <div className="flex items-center space-x-2">
              <div className="w-6 h-6 rounded-full bg-slate-300 flex items-center justify-center">
                <span className="material-icons-round text-slate-500 text-xs">store</span>
              </div>
              <span className="text-xs text-foreground">Store (Closed)</span>
            </div>
          </div>
        </div>

        {/* Floor Selector */}
        <div className="absolute top-4 right-4 bg-card/90 backdrop-blur-sm rounded-xl p-2 shadow-lg border border-slate-200 dark:border-slate-700">
          <div className="flex flex-col space-y-1">
            {['L2', 'L1', 'GF'].map((floor, index) => (
              <button
                key={floor}
                className={`px-4 py-2 rounded-lg text-sm font-semibold transition-colors ${
                  index === 1 ? 'bg-primary text-white' : 'text-muted-foreground hover:bg-slate-100 dark:hover:bg-slate-800'
                }`}
              >
                {floor}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

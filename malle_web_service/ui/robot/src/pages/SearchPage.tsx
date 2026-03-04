import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useRobotStore } from '@/stores/robotStore';
import type { StoreRes } from '@/api/services';
import { toast } from 'sonner';

export function SearchPage() {
  const [query, setQuery] = useState('');
  const [activeCategory, setActiveCategory] = useState('All');
  const { addToGuideQueue, lockboxSlots, setPendingPickupStore, storeList } = useRobotStore();
  const navigate = useNavigate();

  const hasEmptySlot = lockboxSlots.some(s => s.status === 'EMPTY');

  // 서버 데이터에서 카테고리 도출
  const storeCategories = useMemo(() => {
    const cats = new Set<string>();
    storeList.forEach(s => { if (s.category) cats.add(s.category); });
    return ['All', ...Array.from(cats).sort()];
  }, [storeList]);

  const filteredStores = useMemo(() => {
    const lowerQuery = query.toLowerCase();
    return storeList.filter(store => {
      const nameMatch = (store.name || '').toLowerCase().includes(lowerQuery);
      const catMatch = (store.category || '').toLowerCase().includes(lowerQuery);
      const matchesQuery = !query || nameMatch || catMatch;
      const matchesCat = activeCategory === 'All' || store.category === activeCategory;
      return matchesQuery && matchesCat;
    });
  }, [storeList, query, activeCategory]);

  const handleAddToGuide = (store: StoreRes) => {
    addToGuideQueue({
      poiId: String(store.poi_id),  // 숫자 poi_id → guide API에서 Number()로 변환
      poiName: store.name || `Store #${store.id}`,
      floor: `(${store.x_m?.toFixed(0) ?? 0}, ${store.y_m?.toFixed(0) ?? 0})`,
      estimatedTime: Math.floor(Math.random() * 5) + 2,
    });
    toast.success(`Added ${store.name} to Guide Queue`, { duration: 2000 });
  };

  const handleOrderPickup = (store: StoreRes) => {
    setPendingPickupStore(String(store.id));
    navigate('/mode/pickup');
  };

  const handleViewOnMap = (storeId: number) => {
    navigate(`/map?highlight=${storeId}`);
  };

  return (
    <div>
      {/* Search Bar */}
      <div className="relative mb-6">
        <span className="absolute left-4 top-1/2 -translate-y-1/2 material-icons-round text-slate-400">search</span>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="w-full pl-12 pr-10 py-4 rounded-2xl bg-card border border-slate-200 dark:border-slate-700 shadow-sm focus:ring-2 focus:ring-primary/50 focus:border-primary text-lg font-medium outline-none transition-all"
          placeholder="Search stores, products..."
        />
        {query && (
          <button
            onClick={() => setQuery('')}
            className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
          >
            <span className="material-icons-round">close</span>
          </button>
        )}
      </div>

      {/* Filter Chips */}
      <div className="flex space-x-3 mb-8 overflow-x-auto hide-scrollbar">
        {storeCategories.map((category) => (
          <button
            key={category}
            onClick={() => setActiveCategory(category)}
            className={activeCategory === category ? 'chip-active' : 'chip-inactive'}
          >
            {category}
          </button>
        ))}
      </div>

      {/* Empty state while loading */}
      {storeList.length === 0 && (
        <div className="text-center py-16 text-muted-foreground">
          <span className="material-icons-round text-6xl mb-4 block">store</span>
          <p className="text-lg font-medium">Loading stores...</p>
        </div>
      )}

      {/* Results Grid */}
      {storeList.length > 0 && (
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredStores.map((store) => (
            <div
              key={store.id}
              className="robot-card-white relative"
            >
              <div className="absolute top-0 right-0 w-28 h-28 bg-primary/5 rounded-bl-[4rem]" />

              <div className="relative z-10">
                <div className="flex items-start justify-between mb-4">
                  <div className="w-20 h-20 rounded-2xl flex items-center justify-center bg-primary/10">
                    <span className="material-icons-round text-3xl text-primary">store</span>
                  </div>
                  <div className="flex items-center space-x-1.5">
                    <span className="w-2 h-2 rounded-full bg-emerald-500" />
                    <span className="text-xs font-medium text-emerald-600">Open</span>
                  </div>
                </div>

                <h3 className="text-xl font-bold text-foreground mb-1">{store.name}</h3>
                <p className="text-sm text-muted-foreground mb-1">{store.category || 'Store'}</p>
                <p className="text-sm text-muted-foreground mb-4">
                  {store.x_m != null ? `(${store.x_m.toFixed(1)}, ${store.y_m?.toFixed(1)})` : '—'}
                </p>

                <div className="flex space-x-2">
                  <button
                    onClick={() => handleAddToGuide(store)}
                    className="flex-1 btn-secondary py-3.5 text-sm"
                  >
                    <span className="material-icons-round text-base mr-1 align-middle">alt_route</span>
                    Add to Guide
                  </button>
                  {hasEmptySlot && (
                    <button
                      onClick={() => handleOrderPickup(store)}
                      className="flex-1 btn-primary py-3.5 text-sm"
                    >
                      <span className="material-icons-round text-base mr-1 align-middle">shopping_bag</span>
                      Order Pickup
                    </button>
                  )}
                </div>

                <button
                  onClick={() => handleViewOnMap(store.id)}
                  className="w-full mt-2 text-sm text-primary font-medium hover:underline"
                >
                  View on Map
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {storeList.length > 0 && filteredStores.length === 0 && (
        <div className="text-center py-16 text-muted-foreground">
          <span className="material-icons-round text-6xl mb-4 block">search_off</span>
          <p className="text-lg font-medium">No results found</p>
          <p className="text-sm">Try a different search term</p>
        </div>
      )}
    </div>
  );
}

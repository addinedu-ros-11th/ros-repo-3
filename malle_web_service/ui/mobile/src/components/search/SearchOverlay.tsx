import { useState, useEffect } from 'react';
import { useAppStore } from '@/store/appStore';
import { useNavigate } from 'react-router-dom';

interface SearchOverlayProps {
  isOpen: boolean;
  onClose: () => void;
}

const filterOptions = ['All', 'Apparels', 'Electronics', 'Services', 'Others', 'Dining'];

const filterCategoryMap: Record<string, string[]> = {
  'All': [],
  'Apparels': ['Fashion & Apparel'],
  'Electronics': ['Electronics'],
  'Services': ['Services'],
  'Others': ['Sports & Outdoor', 'Fitness'],
  'Dining': ['Dining'],
};

const categoryColors: Record<string, string> = {
  'Fashion & Apparel': 'bg-indigo-50',
  'Sports & Outdoor': 'bg-orange-50',
  'Electronics': 'bg-blue-50',
  'Fitness': 'bg-green-50',
  'Dining': 'bg-amber-50',
};

const categoryDecorations: Record<string, string> = {
  'Fashion & Apparel': 'bg-purple-500/5',
  'Sports & Outdoor': 'bg-orange-500/5',
  'Electronics': 'bg-blue-500/5',
  'Fitness': 'bg-green-500/5',
  'Dining': 'bg-amber-500/5',
};

export function SearchOverlay({ isOpen, onClose }: SearchOverlayProps) {
  const navigate = useNavigate();
  const { 
    searchState, 
    setSearchQuery, 
    setSearchFilter,
    addToGuideQueue,
    pois,
    stores,
    sessionState,
    session,
    taskMission,
  } = useAppStore();

  // const [favorites, setFavorites] = useState<Set<string>>(new Set());
  const [favorites, setFavorites] = useState<Record<string, boolean>>({});
  const [toast, setToast] = useState<string | null>(null);

  // Custom filtering with new categories
  const getFilteredResults = () => {
    return stores.filter((store) => {
      const matchesQuery = store.name.toLowerCase().includes(searchState.query.toLowerCase()) ||
        store.category.toLowerCase().includes(searchState.query.toLowerCase());
      
      if (searchState.filter === 'All') return matchesQuery;
      
      const categories = filterCategoryMap[searchState.filter] || [];
      return matchesQuery && categories.includes(store.category);
    });
  };

  const filteredResults = getFilteredResults();

  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  if (!isOpen) return null;

  const isActive = sessionState === 'ACTIVE';
  const isTaskMode = isActive && session.type === 'TASK' && !!taskMission;

  const handleAddToGuide = (storeId: string, storeName: string) => {
    if (isTaskMode) return;
    const poi = pois.find(p => p.id === storeId);
    if (poi) {
      addToGuideQueue(poi);
      setToast(`${storeName} added to your Queue`);
    }
  };

  const toggleFavorite = (storeId: string) => {
    console.log('toggle:', storeId, typeof storeId);
    console.log('before:', favorites);
    setFavorites(prev => ({
      ...prev,
      [storeId]: !prev[storeId],
    }));
  };

  return (
    <div className="fixed inset-0 z-50 bg-background/95 backdrop-blur-xl flex flex-col">
      {/* Search Header */}
      <div className="pt-14 pb-4 px-5 bg-card/60 backdrop-blur-md border-b border-border/50 sticky top-0 z-10">
        <div className="flex items-center gap-3">
          <div className="flex-1 relative">
            <span className={`material-icons-round absolute left-4 top-1/2 -translate-y-1/2 text-xl transition-colors ${
              searchState.query ? 'text-primary' : 'text-muted-foreground'
            }`}>
              search
            </span>
            <input
              type="text"
              placeholder="Search stores, products..."
              value={searchState.query}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-12 pr-10 py-3.5 rounded-2xl bg-card border-none shadow-sm focus:ring-2 focus:ring-primary/50 text-base font-medium outline-none"
              autoFocus
            />
            {searchState.query && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-4 top-1/2 -translate-y-1/2"
              >
                <span className="material-icons-round text-muted-foreground text-xl">close</span>
              </button>
            )}
          </div>
          <button
            onClick={onClose}
            className="text-sm font-semibold text-primary"
          >
            Cancel
          </button>
        </div>

        {/* Filter Chips */}
        <div className="flex gap-2 mt-4 overflow-x-auto hide-scrollbar pb-1">
          {filterOptions.map((filter) => (
            <button
              key={filter}
              onClick={() => setSearchFilter(filter)}
              className={`px-5 py-2.5 rounded-2xl text-sm font-semibold whitespace-nowrap transition-all active-press-sm ${
                searchState.filter === filter
                  ? 'bg-primary text-primary-foreground shadow-lg shadow-primary/30 border border-primary'
                  : 'bg-card border border-border text-muted-foreground hover:bg-muted'
              }`}
            >
              {filter}
            </button>
          ))}
        </div>
      </div>

      {/* Results */}
      <div className="flex-1 overflow-y-auto px-5 py-6 space-y-4 pb-32 hide-scrollbar">
        <div className="flex justify-between items-center">
          <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider">
            {filteredResults.length} Results
          </span>
        </div>

        {filteredResults.map((store) => (
          <div
            key={store.id}
            className={`bg-card rounded-[1.75rem] p-5 shadow-card border border-border/50 relative overflow-hidden transition-all active-press ${
              !store.open ? 'opacity-60' : ''
            }`}
          >
            {/* Decoration */}
            <div className={`absolute top-0 right-0 w-24 h-24 rounded-bl-[4rem] pointer-events-none ${categoryDecorations[store.category] || 'bg-gray-500/5'}`} />

            <div className="flex gap-4">
              {/* Icon */}
              <div className={`w-16 h-16 rounded-2xl flex items-center justify-center shrink-0 ${categoryColors[store.category] || 'bg-muted'}`}>
                <span className="material-icons-round text-2xl text-foreground/70">{store.icon}</span>
              </div>

              {/* Info */}
              <div className="flex-1 min-w-0">
                <div className="flex justify-between items-start">
                  <div>
                    <h3 className="text-lg font-bold text-foreground">{store.name}</h3>
                    <p className="text-xs text-muted-foreground">{store.category} • {store.location}</p>
                  </div>
                  <button
                    className="p-2 -m-1 active:scale-125 transition-transform"
                    onClick={(e) => {
                      e.stopPropagation();
                      e.preventDefault();
                      toggleFavorite(store.id);
                    }}
                  >
                    <span className={`material-icons-round text-xl transition-colors ${favorites[store.id] ? 'text-red-500' : 'text-muted-foreground/60'}`}>
                      {favorites[store.id] ? 'favorite' : 'favorite_border'}
                    </span>
                  </button>
                </div>

                {/* Status */}
                <div className="flex items-center gap-1.5 mt-2">
                  {store.open ? (
                    <>
                      <span className="w-2 h-2 bg-emerald-500 rounded-full"></span>
                      <span className="text-[11px] font-semibold text-emerald-600">
                        Open until {store.closeTime}
                      </span>
                    </>
                  ) : (
                    <>
                      <span className="w-2 h-2 bg-muted-foreground rounded-full"></span>
                      <span className="text-[11px] font-semibold text-muted-foreground">
                        Opens at {store.openTime}
                      </span>
                    </>
                  )}
                </div>

                {/* Actions */}
                <div className="flex gap-3 mt-4">
                  {store.open ? (
                    <>
                      <button
                        onClick={() => handleAddToGuide(store.id, store.name)}
                        disabled={isTaskMode}
                        className="flex items-center gap-1.5 px-4 py-2 border border-border rounded-xl text-xs font-bold text-foreground hover:bg-muted transition-colors active-press-sm disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <span className="material-icons-round text-base">alt_route</span>
                        Add to Guide
                      </button>
                      <button
                        onClick={() => {
                          if (isTaskMode) return;
                          onClose();
                          navigate('/mode/pickup');
                        }}
                        disabled={isTaskMode}
                        className="flex items-center gap-1.5 px-4 py-2 bg-primary text-primary-foreground rounded-xl text-xs font-bold shadow-lg shadow-primary/20 active-press-sm disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <span className="material-icons-round text-base">shopping_bag</span>
                        Order Pickup
                      </button>
                    </>
                  ) : (
                    <button
                      disabled
                      className="flex items-center gap-1.5 px-4 py-2 border-2 border-dashed border-muted-foreground/30 rounded-xl text-xs font-bold text-muted-foreground cursor-not-allowed w-full justify-center"
                    >
                      <span className="material-icons-round text-base">lock_clock</span>
                      Store Closed
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* View on Map FAB */}
      <button
        onClick={() => {
          onClose();
          navigate('/map');
        }}
        className="fixed bottom-24 right-6 z-40 bg-foreground text-background rounded-full shadow-2xl pl-5 pr-6 py-4 flex items-center gap-2 hover:scale-105 transition-transform active-press-sm"
      >
        <span className="material-icons-round text-2xl">map</span>
        <span className="font-bold text-sm tracking-wide">View on Map</span>
      </button>

      {/* Toast notification */}
      {toast && (
        <div className="fixed bottom-28 left-1/2 -translate-x-1/2 z-[60] bg-foreground text-background px-5 py-3 rounded-2xl shadow-2xl flex items-center gap-2 animate-fade-in">
          <span className="material-icons-round text-lg text-emerald-400">check_circle</span>
          <span className="text-sm font-semibold">{toast}</span>
        </div>
      )}
    </div>
  );
}

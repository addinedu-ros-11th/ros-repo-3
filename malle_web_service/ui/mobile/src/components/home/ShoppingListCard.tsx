import { useNavigate } from 'react-router-dom';
import { useAppStore } from '@/store/appStore';

export function ShoppingListCard() {
  const navigate = useNavigate();
  const { shoppingList } = useAppStore();
  
  const pendingItems = shoppingList.filter(item => !item.completed);
  const completedCount = shoppingList.filter(item => item.completed).length;
  const totalCount = shoppingList.length;

  return (
    <div 
      onClick={() => navigate('/list')}
      className="bg-card-blue dark:bg-blue-900/40 rounded-3xl p-5 h-44 relative overflow-hidden active-press cursor-pointer"
    >
      {/* Decoration */}
      <div className="card-decoration right-0 top-0 w-32 h-32 bg-cyan-300/20" />

      <div className="relative z-10 h-full flex flex-col">
        {/* Header */}
        <div className="flex justify-between items-start">
          <div className="bg-white/20 p-2 rounded-xl backdrop-blur-sm">
            <span className="material-icons-round text-white text-xl">shopping_cart</span>
          </div>
          <span className="text-xs font-bold bg-white text-blue-600 px-2 py-1 rounded-full">
            {completedCount}/{totalCount}
          </span>
        </div>

        {/* Title */}
        <h3 className="text-xl font-bold text-white mt-3">Shopping List</h3>

        {/* Preview Items */}
        <div className="mt-auto space-y-1.5">
          {pendingItems.slice(0, 2).map((item) => (
            <div key={item.id} className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 bg-white rounded-full shrink-0" />
              <span className="text-white text-sm truncate">{item.name}</span>
            </div>
          ))}
          {pendingItems.length > 2 && (
            <p className="text-white/60 text-xs italic">
              + {pendingItems.length - 2} more items
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

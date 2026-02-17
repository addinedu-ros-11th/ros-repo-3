import { useNavigate } from 'react-router-dom';
import { useAppStore } from '@/store/appStore';

export function LockboxCapacityCard() {
  const navigate = useNavigate();
  const { lockboxSlots } = useAppStore();
  
  const occupiedSlots = lockboxSlots.filter(s => s.status !== 'EMPTY').length;
  const totalSlots = lockboxSlots.length;

  return (
    <div 
      onClick={() => navigate('/lockbox')}
      className="bg-card-lime dark:bg-lime-900/40 rounded-3xl p-5 h-44 relative overflow-hidden active-press cursor-pointer"
    >
      {/* Decoration */}
      <div className="card-decoration -left-4 -bottom-4 w-24 h-24 bg-yellow-300/30" />

      <div className="relative z-10 h-full flex flex-col">
        {/* Header */}
        <div className="flex justify-between items-start">
          <div className="bg-white/50 dark:bg-white/20 p-2 rounded-xl backdrop-blur-sm">
            <span className="material-icons-round text-lime-900 dark:text-lime-100 text-xl">lock</span>
          </div>
          <button className="w-8 h-8 rounded-full bg-lime-900 dark:bg-lime-100 flex items-center justify-center">
            <span className="material-icons-round text-white dark:text-lime-900 text-lg">add</span>
          </button>
        </div>

        {/* Content */}
        <div className="mt-auto">
          <p className="text-sm font-medium text-lime-900 dark:text-lime-100">Lockbox Capacity</p>
          <div className="flex items-baseline gap-1">
            <span className="text-3xl font-bold text-lime-950 dark:text-lime-50">{occupiedSlots}</span>
            <span className="text-lg text-lime-700 dark:text-lime-200 font-normal">/{totalSlots}</span>
          </div>
          <p className="text-xs text-lime-800 dark:text-lime-200">Slots occupied</p>
        </div>
      </div>
    </div>
  );
}

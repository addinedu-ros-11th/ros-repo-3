import { useNavigate } from 'react-router-dom';
import { useAppStore } from '@/store/appStore';

export function FindRobotBar() {
  const navigate = useNavigate();
  const { robot } = useAppStore();

  return (
    <div className="bg-card rounded-2xl p-4 border border-border shadow-sm flex items-center gap-4 active-press">
      <div className="bg-indigo-100 dark:bg-indigo-900/50 p-2.5 rounded-xl">
        <span className="material-icons-round text-indigo-600 dark:text-indigo-300 text-xl">location_searching</span>
      </div>
      
      <div className="flex-1">
        <h4 className="font-semibold text-foreground">Find {robot?.name}</h4>
        <p className="text-xs text-muted-foreground">Level 1, Zone A • Near Nike Store</p>
      </div>

      <button 
        onClick={() => navigate('/map')}
        className="text-sm font-semibold text-primary"
      >
        Show Map
      </button>
    </div>
  );
}

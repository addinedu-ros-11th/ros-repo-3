import { useNavigate } from 'react-router-dom';
import { useDashboard } from '@/context/DashboardContext';
import { MI } from './MaterialIcon';

export default function EmergencyBanner() {
  const { emergencyBanner, dismissEmergency } = useDashboard();
  const navigate = useNavigate();

  if (!emergencyBanner?.active) return null;

  return (
    <div className="bg-critical-red text-primary-foreground px-6 py-2 flex items-center justify-between sticky top-0 z-50 animate-pulse">
      <div className="flex items-center gap-3">
        <MI icon="report_problem" className="text-xl" />
        <span className="font-semibold text-sm">
          EMERGENCY: {emergencyBanner.message}
        </span>
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={() => {
            navigate('/manual-control');
          }}
          className="bg-white/20 hover:bg-white/30 px-4 py-1 rounded-full text-xs font-bold transition-all"
        >
          TAKE OVER
        </button>
        <button
          onClick={dismissEmergency}
          className="bg-white/20 hover:bg-white/30 p-1 rounded-full transition-all"
        >
          <MI icon="close" className="text-sm" />
        </button>
      </div>
    </div>
  );
}

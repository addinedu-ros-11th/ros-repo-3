import { useNavigate } from 'react-router-dom';
import { useAppStore } from '@/store/appStore';

export function TaskActiveCard() {
  const navigate = useNavigate();
  const { taskMission, robot } = useAppStore();

  if (!taskMission) return null;

  const isGuide = taskMission.type === 'GUIDE';
  const isPickup = taskMission.type === 'PICKUP';

  const handleGoToMission = () => {
    if (isGuide) {
      navigate('/mode/guide/active');
    } else if (isPickup) {
      navigate('/mode/pickup');
    }
  };

  return (
    <div className="bg-gradient-to-br from-violet-500 to-purple-600 rounded-3xl p-6 relative overflow-hidden active-press">
      {/* Decoration */}
      <div className="card-decoration -right-6 -top-6 w-32 h-32 bg-white/20" />
      <div className="card-decoration -left-4 -bottom-4 w-20 h-20 bg-white/10" />

      <div className="relative z-10">
        {/* Header */}
        <div className="flex justify-between items-start mb-4">
          <div>
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/20 text-white text-xs font-bold mb-2">
              <span className="material-icons-round text-sm">task_alt</span>
              Task Mode
            </div>
            <h2 className="text-2xl font-bold text-white">
              {isGuide ? 'Guide Mission' : 'Pickup Mission'}
            </h2>
          </div>
        </div>

        {/* Mission Info */}
        <div className="bg-white/10 backdrop-blur-sm rounded-2xl p-4 mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center">
              <span className="material-icons-round text-white text-xl">
                {isGuide ? 'alt_route' : 'shopping_bag'}
              </span>
            </div>
            <div className="flex-1">
              {isGuide && taskMission.destinationPoi && (
                <>
                  <p className="text-white font-medium">{taskMission.destinationPoi.name}</p>
                  <p className="text-white/60 text-xs">Destination</p>
                </>
              )}
              {isPickup && (
                <>
                  <p className="text-white font-medium">{taskMission.storeName}</p>
                  <p className="text-white/60 text-xs">
                    {taskMission.items?.length} item{(taskMission.items?.length || 0) > 1 ? 's' : ''} to pickup
                  </p>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Robot info */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <span className="material-icons-round text-white/70 text-lg">smart_toy</span>
            <span className="text-white/70 text-sm">{robot?.name}</span>
          </div>
          <span className="text-white/70 text-sm">{robot?.battery}% battery</span>
        </div>

        {/* Go to Mission Button */}
        <button
          onClick={handleGoToMission}
          className="w-full py-3.5 rounded-2xl bg-white text-violet-600 font-bold shadow-lg active-press-sm flex items-center justify-center gap-2"
        >
          <span className="material-icons-round">arrow_forward</span>
          Go to Mission
        </button>
      </div>
    </div>
  );
}

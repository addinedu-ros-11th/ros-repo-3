import { useNavigate } from 'react-router-dom';
import { useAppStore } from '@/store/appStore';

export default function TaskComplete() {
  const navigate = useNavigate();
  const { taskMission, robot, endSession } = useAppStore();

  const isGuide = taskMission?.type === 'GUIDE';
  const isPickup = taskMission?.type === 'PICKUP';

  const handleNewSession = () => {
    endSession();
    navigate('/');
    // The user will open the modal from Home
  };

  const handleGoHome = () => {
    endSession();
    navigate('/');
  };

  return (
    <div className="space-y-6 flex flex-col items-center pt-8">
      {/* Success Icon */}
      <div className="w-24 h-24 rounded-full bg-emerald-100 dark:bg-emerald-900/40 flex items-center justify-center">
        <span className="material-icons-round text-5xl text-emerald-500">check_circle</span>
      </div>

      <div className="text-center">
        <h1 className="text-3xl font-bold tracking-tight text-foreground">Task Complete!</h1>
        <p className="text-muted-foreground text-sm mt-2">Your mission has been successfully completed.</p>
      </div>

      {/* Mission Summary Card */}
      <div className="w-full bg-card rounded-3xl p-5 border border-border">
        <h3 className="font-bold text-foreground mb-3 flex items-center gap-2">
          <span className="material-icons-round text-primary text-lg">
            {isGuide ? 'alt_route' : 'shopping_bag'}
          </span>
          Mission Summary
        </h3>

        {isGuide && taskMission?.destinationPoi && (
          <div className="bg-muted rounded-2xl p-4">
            <p className="text-sm font-medium text-foreground">{taskMission.destinationPoi.name}</p>
            <p className="text-xs text-muted-foreground mt-1">Guide destination reached</p>
          </div>
        )}

        {isPickup && taskMission?.items && (
          <div className="space-y-2">
            <div className="bg-muted rounded-2xl p-4">
              <p className="text-sm font-semibold text-foreground mb-2">{taskMission.storeName}</p>
              {taskMission.items.map((item, idx) => (
                <div key={idx} className="flex justify-between text-sm py-1">
                  <span className="text-muted-foreground">{item.name} × {item.quantity}</span>
                  <span className="font-medium text-foreground">${(item.price * item.quantity).toFixed(2)}</span>
                </div>
              ))}
              <div className="border-t border-border mt-2 pt-2 flex justify-between">
                <span className="font-semibold text-foreground">Total</span>
                <span className="font-bold text-foreground">
                  ${taskMission.items.reduce((a, b) => a + b.price * b.quantity, 0).toFixed(2)}
                </span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Robot Return Card */}
      <div className="w-full bg-muted rounded-2xl p-4 flex items-center gap-3">
        <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
          <span className="material-icons-round text-primary">smart_toy</span>
        </div>
        <div>
          <p className="text-sm font-medium text-foreground">{robot?.name || 'Mall·E'} returned</p>
          <p className="text-xs text-muted-foreground">Robot has been released back to the fleet</p>
        </div>
      </div>

      {/* Actions */}
      <div className="w-full space-y-3 pt-2">
        <button
          onClick={handleNewSession}
          className="w-full py-4 rounded-2xl bg-primary text-primary-foreground font-bold shadow-lg shadow-primary/30 active-press-sm flex items-center justify-center gap-2"
        >
          <span className="material-icons-round">add</span>
          Start New Session
        </button>
        <button
          onClick={handleGoHome}
          className="w-full py-4 rounded-2xl border border-border text-foreground font-bold active-press-sm flex items-center justify-center gap-2"
        >
          <span className="material-icons-round">home</span>
          Back to Home
        </button>
      </div>
    </div>
  );
}

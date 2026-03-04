import { useNavigate } from 'react-router-dom';
import { useAppStore } from '@/store/appStore';
import { guideApi } from '@/api/guide';

export default function GuideActive() {
  const navigate = useNavigate();
  const { guideQueue, completeCurrentGuide, setRobotMode, session, completeTaskSession } = useAppStore();

  const currentGuide = guideQueue.find(item => item.status === 'IN_PROGRESS');
  const pendingCount = guideQueue.filter(item => item.selected && item.status === 'PENDING').length;
  const completedCount = guideQueue.filter(item => item.status === 'DONE').length;

  const handleComplete = async () => {
    const { currentSessionId } = useAppStore.getState();
    if (currentSessionId) {
      await guideApi.advance(currentSessionId).catch(() => {});
    }
    completeCurrentGuide();
    const remaining = guideQueue.filter(item => item.selected && item.status === 'PENDING').length;
    if (remaining === 0) {
      setRobotMode(null);
      if (session.type === 'TASK') {
        completeTaskSession();
        navigate('/task-complete');
      } else {
        navigate('/mode/guide');
      }
    }
  };  

  // const handleComplete = () => {
  //   completeCurrentGuide();
  //   const remaining = guideQueue.filter(item => item.selected && item.status === 'PENDING').length;
  //   if (remaining === 0) {
  //     setRobotMode(null);
  //     if (session.type === 'TASK') {
  //       completeTaskSession();
  //       navigate('/task-complete');
  //     } else {
  //       navigate('/mode/guide');
  //     }
  //   }
  // };

  const handleCancel = () => {
    setRobotMode(null);
    navigate('/mode/guide');
  };

  if (!currentGuide) {
    return (
      <div className="space-y-5">
        <div className="text-center py-12">
          <span className="material-icons-round text-6xl text-emerald-500 mb-4">check_circle</span>
          <h2 className="text-2xl font-bold text-foreground mb-2">All Done!</h2>
          <p className="text-muted-foreground mb-6">You've completed all destinations</p>
          <button
            onClick={() => navigate('/mode')}
            className="px-6 py-3 rounded-xl bg-primary text-primary-foreground font-semibold active-press-sm"
          >
            Back to Modes
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div>
        <button onClick={handleCancel} className="flex items-center gap-1 text-primary mb-2">
          <span className="material-icons-round text-sm">close</span>
          <span className="text-sm font-medium">Cancel Guide</span>
        </button>
        <h1 className="text-3xl font-bold tracking-tight text-foreground">Navigating</h1>
        <p className="text-muted-foreground text-sm mt-1">
          {completedCount} completed • {pendingCount} remaining
        </p>
      </div>

      {/* Current Destination Card */}
      <div className="bg-gradient-to-br from-blue-500 to-indigo-600 rounded-3xl p-6 relative overflow-hidden">
        <div className="card-decoration -right-10 -top-10 w-40 h-40 bg-white/20" />

        <div className="relative z-10">
          <div className="flex items-center gap-2 mb-4">
            <span className="w-3 h-3 bg-white rounded-full animate-pulse" />
            <span className="text-white/80 text-sm font-medium">Currently navigating to</span>
          </div>

          <h2 className="text-3xl font-bold text-white mb-2">{currentGuide.poiName}</h2>
          <p className="text-white/70">{currentGuide.floor}</p>

          <div className="mt-6 bg-white/10 backdrop-blur-sm rounded-2xl p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="material-icons-round text-white text-2xl">near_me</span>
                <div>
                  <p className="text-white font-medium">In Progress</p>
                  <p className="text-white/60 text-sm">~{currentGuide.estimatedTime} min remaining</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Upcoming */}
      {pendingCount > 0 && (
        <div className="bg-card rounded-2xl p-4 border border-border">
          <h3 className="font-semibold text-foreground mb-3 flex items-center gap-2">
            <span className="material-icons-round text-muted-foreground text-lg">upcoming</span>
            Up Next
          </h3>
          <div className="space-y-2">
            {guideQueue
              .filter(item => item.selected && item.status === 'PENDING')
              .slice(0, 3)
              .map((item) => (
                <div key={item.id} className="flex items-center gap-3 py-2">
                  <span className="w-2 h-2 bg-muted-foreground rounded-full" />
                  <span className="text-sm text-foreground">{item.poiName}</span>
                  <span className="text-xs text-muted-foreground ml-auto">~{item.estimatedTime} min</span>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="fixed bottom-28 left-5 right-5 max-w-[430px] mx-auto">
        <button
          onClick={handleComplete}
          className="w-full py-4 rounded-2xl bg-emerald-500 text-white font-bold text-lg shadow-lg shadow-emerald-500/30 active-press-sm flex items-center justify-center gap-2"
        >
          <span className="material-icons-round">check</span>
          Mark as Arrived
        </button>
      </div>
    </div>
  );
}

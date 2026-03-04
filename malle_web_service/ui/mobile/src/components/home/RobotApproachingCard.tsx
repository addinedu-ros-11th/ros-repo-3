import { useAppStore } from '@/store/appStore';

export function RobotApproachingCard() {
  const { robot, sessionState, approachingEta } = useAppStore();

  if (sessionState === 'FINDING_ROBOT') {
    return (
      <div className="bg-gradient-to-br from-amber-400 to-orange-500 rounded-3xl p-6 relative overflow-hidden">
        <div className="card-decoration -right-10 -top-10 w-40 h-40 bg-white/20" />
        
        <div className="relative z-10 flex items-center gap-4">
          <div className="w-16 h-16 rounded-2xl bg-white/20 backdrop-blur-sm flex items-center justify-center">
            <span className="material-icons-round text-white text-3xl animate-pulse">search</span>
          </div>
          <div>
            <h2 className="text-xl font-bold text-white">Finding Robot...</h2>
            <p className="text-white/70 text-sm">Please wait while we find you a robot</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-gradient-to-br from-emerald-400 to-teal-500 rounded-3xl p-6 relative overflow-hidden">
      <div className="card-decoration -right-10 -top-10 w-40 h-40 bg-white/20" />
      <div className="card-decoration -left-6 -bottom-6 w-24 h-24 bg-cyan-300/20" />

      <div className="relative z-10">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-14 h-14 rounded-2xl bg-white/20 backdrop-blur-sm flex items-center justify-center">
              <span className="material-icons-round text-white text-2xl">smart_toy</span>
            </div>
            <div>
              <p className="text-white/70 text-xs font-medium">Assigned Robot</p>
              <h3 className="text-white font-bold text-lg">{robot?.name}</h3>
            </div>
          </div>
          <div className="text-right">
            <p className="text-white/70 text-xs">Battery</p>
            <p className="text-white font-bold">{robot?.battery}%</p>
          </div>
        </div>

        <div className="bg-white/10 backdrop-blur-sm rounded-2xl p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="material-icons-round text-white animate-pulse-ring">near_me</span>
              <span className="text-white font-medium">Approaching...</span>
            </div>
            <div className="bg-white/20 rounded-full px-4 py-2">
              <span className="text-white font-bold">{approachingEta}s ETA</span>
            </div>
          </div>
        </div>

        <p className="text-white/60 text-xs text-center mt-4">
          Robot is on its way to your location
        </p>
      </div>
    </div>
  );
}

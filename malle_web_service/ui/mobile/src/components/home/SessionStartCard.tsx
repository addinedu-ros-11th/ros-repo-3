interface SessionStartCardProps {
  onStart: () => void;
}

export function SessionStartCard({ onStart }: SessionStartCardProps) {
  return (
    <div className="bg-gradient-to-br from-primary to-blue-600 rounded-3xl p-6 relative overflow-hidden active-press">
      {/* Decoration */}
      <div className="card-decoration -right-10 -top-10 w-40 h-40 bg-white/20" />
      <div className="card-decoration -left-6 -bottom-6 w-32 h-32 bg-cyan-300/20" />

      <div className="relative z-10">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-10 h-10 rounded-xl bg-white/20 backdrop-blur-sm flex items-center justify-center">
            <span className="material-icons-round text-white text-xl">smart_toy</span>
          </div>
          <span className="text-white/80 text-sm font-medium">Mall·E</span>
        </div>

        <h2 className="text-2xl font-bold text-white mb-2">Start Your Session</h2>
        <p className="text-white/70 text-sm mb-6">
          Get paired with a robot assistant for your shopping journey
        </p>

        <button 
          onClick={onStart}
          className="w-full bg-white text-primary py-4 rounded-2xl font-bold text-lg shadow-lg shadow-black/10 hover:bg-white/95 transition-colors active-press-sm flex items-center justify-center gap-2"
        >
          <span className="material-icons-round">play_arrow</span>
          Start Session
        </button>
      </div>
    </div>
  );
}

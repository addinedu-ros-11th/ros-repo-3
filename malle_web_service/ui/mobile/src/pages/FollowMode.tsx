import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppStore, FollowStatus } from '@/store/appStore';

const tagOptions: (11 | 12 | 13)[] = [11, 12, 13];

export default function FollowMode() {
  const navigate = useNavigate();
  const { followMe, startFollowMe, stopFollowMe, setFollowStatus, sessionState, session, taskMission } = useAppStore();
  const [selectedTag, setSelectedTag] = useState<11 | 12 | 13>(followMe.tagNumber ?? 11);
  const [changingTag, setChangingTag] = useState(false);

  const isActive = sessionState === 'ACTIVE';
  const isTaskMode = isActive && session.type === 'TASK' && !!taskMission;

  // Redirect/block if in task mode
  if (isTaskMode) {
    return (
      <div className="space-y-5">
        <div>
          <button onClick={() => navigate('/mode')} className="flex items-center gap-1 text-primary mb-2">
            <span className="material-icons-round text-sm">arrow_back</span>
            <span className="text-sm font-medium">Back to Modes</span>
          </button>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Follow Me</h1>
        </div>

        <div className="bg-muted rounded-3xl p-8 text-center">
          <div className="w-20 h-20 rounded-full bg-background mx-auto flex items-center justify-center mb-4">
            <span className="material-icons-round text-4xl text-muted-foreground">block</span>
          </div>
          <h3 className="font-bold text-lg text-foreground mb-2">사용할 수 없습니다</h3>
          <p className="text-sm text-muted-foreground mb-4">
            Follow Me 모드는 Time 세션에서만 사용 가능합니다.
          </p>
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

  const handleStart = () => {
    startFollowMe(selectedTag);
  };

  const handleStop = () => {
    stopFollowMe();
  };

  const getStatusColor = (status: FollowStatus) => {
    switch (status) {
      case 'FOLLOWING': return 'text-emerald-500 bg-emerald-100 dark:bg-emerald-900/50';
      case 'LOST': return 'text-red-500 bg-red-100 dark:bg-red-900/50';
      case 'STOPPED': return 'text-muted-foreground bg-muted';
      case 'RECONNECTING': return 'text-amber-500 bg-amber-100 dark:bg-amber-900/50';
    }
  };

  const getStatusIcon = (status: FollowStatus) => {
    switch (status) {
      case 'FOLLOWING': return 'directions_run';
      case 'LOST': return 'signal_wifi_off';
      case 'STOPPED': return 'pause_circle';
      case 'RECONNECTING': return 'sync';
    }
  };

  return (
    <div className="space-y-5">
      {/* Header */}
      <div>
        <button onClick={() => navigate('/mode')} className="flex items-center gap-1 text-primary mb-2">
          <span className="material-icons-round text-sm">arrow_back</span>
          <span className="text-sm font-medium">Back to Modes</span>
        </button>
        <h1 className="text-3xl font-bold tracking-tight text-foreground">Follow Me</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Robot will follow you using AprilTag tracking
        </p>
      </div>

      {/* Status Card */}
      {followMe.active ? (
        <div className="bg-gradient-to-br from-emerald-500 to-teal-600 rounded-3xl p-6 relative overflow-hidden">
          <div className="card-decoration -right-10 -top-10 w-40 h-40 bg-white/20" />

          <div className="relative z-10">
            <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full ${getStatusColor(followMe.status)} mb-4`}>
              <span className={`material-icons-round text-lg ${followMe.status === 'RECONNECTING' ? 'animate-spin' : ''}`}>
                {getStatusIcon(followMe.status)}
              </span>
              <span className="font-semibold text-sm capitalize">{followMe.status.toLowerCase()}</span>
            </div>

            <h2 className="text-2xl font-bold text-white mb-2">Following You</h2>
            <p className="text-white/70 mb-4">AprilTag #{followMe.tagNumber}</p>

            {changingTag ? (
              <div className="mb-2">
                <p className="text-white/70 text-sm mb-2">Select new AprilTag</p>
                <div className="grid grid-cols-3 gap-2 mb-3">
                  {tagOptions.map((tag) => (
                    <button
                      key={tag}
                      onClick={() => setSelectedTag(tag)}
                      className={`py-3 rounded-xl font-bold transition-all active-press-sm ${
                        selectedTag === tag
                          ? 'bg-white text-teal-600 shadow-md'
                          : 'bg-white/20 text-white hover:bg-white/30'
                      }`}
                    >
                      #{tag}
                    </button>
                  ))}
                </div>
                <div className="flex gap-3">
                  <button
                    onClick={() => setChangingTag(false)}
                    className="flex-1 py-3 rounded-xl bg-white/20 backdrop-blur-sm text-white font-semibold active-press-sm"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() => {
                      startFollowMe(selectedTag);
                      setChangingTag(false);
                    }}
                    className="flex-1 py-3 rounded-xl bg-white text-teal-600 font-semibold active-press-sm"
                  >
                    Confirm
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex gap-3">
                <button
                  onClick={() => {
                    setSelectedTag(followMe.tagNumber ?? 11);
                    setChangingTag(true);
                  }}
                  className="flex-1 py-3 rounded-xl bg-white/20 backdrop-blur-sm text-white font-semibold active-press-sm"
                >
                  Change Tag
                </button>
                <button
                  onClick={handleStop}
                  className="flex-1 py-3 rounded-xl bg-white text-teal-600 font-semibold active-press-sm"
                >
                  Stop Following
                </button>
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="bg-card rounded-3xl p-6 border border-border">
          <div className="text-center mb-6">
            <div className="w-20 h-20 rounded-full bg-muted mx-auto flex items-center justify-center mb-4">
              <span className="material-icons-round text-4xl text-muted-foreground">directions_run</span>
            </div>
            <h3 className="font-bold text-lg text-foreground">Ready to Follow</h3>
            <p className="text-sm text-muted-foreground mt-1">Select your AprilTag number to begin</p>
          </div>

          {/* Tag Selection */}
          <div className="mb-6">
            <p className="text-sm font-medium text-muted-foreground mb-3">Select AprilTag</p>
            <div className="grid grid-cols-3 gap-3">
              {tagOptions.map((tag) => (
                <button
                  key={tag}
                  onClick={() => setSelectedTag(tag)}
                  className={`py-4 rounded-xl font-bold transition-all active-press-sm ${
                    selectedTag === tag
                      ? 'bg-primary text-primary-foreground shadow-md ring-2 ring-primary ring-offset-2'
                      : 'bg-muted text-muted-foreground hover:bg-muted/80'
                  }`}
                >
                  #{tag}
                </button>
              ))}
            </div>
          </div>

          <button
            onClick={handleStart}
            disabled={!isActive}
            className="w-full py-4 rounded-xl bg-primary text-primary-foreground font-bold shadow-lg shadow-primary/30 active-press-sm disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            <span className="material-icons-round">play_arrow</span>
            Start Following
          </button>
        </div>
      )}

      {/* Simulate Status Change (Demo Only) */}
      {followMe.active && (
        <div className="bg-muted rounded-2xl p-4">
          <p className="text-xs font-medium text-muted-foreground mb-3">Demo: Simulate Status</p>
          <div className="flex flex-wrap gap-2">
            {(['FOLLOWING', 'LOST', 'RECONNECTING'] as FollowStatus[]).map((status) => (
              <button
                key={status}
                onClick={() => setFollowStatus(status)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  followMe.status === status
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-card text-muted-foreground hover:bg-card/80'
                }`}
              >
                {status}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

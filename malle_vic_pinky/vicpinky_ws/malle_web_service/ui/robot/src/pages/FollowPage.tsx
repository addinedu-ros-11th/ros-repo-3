import { useRobotStore } from '@/stores/robotStore';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { FollowTag, FollowStatus } from '@/types/robot';
import { api } from '@/api/client';

export function FollowPage() {
  const { follow, startFollow, stopFollow, setFollowStatus, changeFollowTag } = useRobotStore();
  const navigate = useNavigate();
  const [showTagDialog, setShowTagDialog] = useState(!follow.active);
  const [selectedTag, setSelectedTag] = useState<FollowTag>(11);

  const handleStartFollow = async () => {
      startFollow(selectedTag);
      setShowTagDialog(false);
      const { currentSessionId } = useRobotStore.getState();
      if (currentSessionId) {
          await api.patch(`/sessions/${currentSessionId}/follow-tag`, {
              tag_code: selectedTag,
              tag_family: 'tag36h11',
          }).catch(() => {});
      }
  };

  const handleChangeTag = () => {
    setShowTagDialog(true);
  };

  const handleConfirmTagChange = async () => {
      changeFollowTag(selectedTag);
      setShowTagDialog(false);
      const { currentSessionId } = useRobotStore.getState();
      if (currentSessionId) {
          await api.patch(`/sessions/${currentSessionId}/follow-tag`, {
              tag_code: selectedTag,
              tag_family: 'tag36h11',
          }).catch(() => {});
      }
  };

  const getStatusColor = (status: FollowStatus) => {
    switch (status) {
      case 'FOLLOWING': return 'text-emerald-500';
      case 'LOST': return 'text-red-500';
      case 'STOPPED': return 'text-amber-500';
      case 'RECONNECTING': return 'text-blue-500 animate-pulse';
    }
  };

  const getStatusIcon = (status: FollowStatus) => {
    switch (status) {
      case 'FOLLOWING': return 'check_circle';
      case 'LOST': return 'error';
      case 'STOPPED': return 'pause_circle';
      case 'RECONNECTING': return 'sync';
    }
  };

  // Demo: Simulate status changes
  const simulateStatus = (status: FollowStatus) => {
    setFollowStatus(status);
  };

  if (!follow.active) {
    return (
      <div>
        <div className="flex items-center space-x-3 mb-8">
          <button onClick={() => navigate('/mode')} className="btn-ghost p-2">
            <span className="material-icons-round">arrow_back</span>
          </button>
          <h1 className="text-page-title">Follow Me Mode</h1>
        </div>

        <div className="max-w-md mx-auto">
          <div className="robot-card-purple text-center py-12">
            <div className="absolute -right-10 -top-10 w-48 h-48 bg-white/15 rounded-full blur-3xl" />
            <div className="relative z-10">
              <span className="material-icons-round text-6xl text-white/80 mb-4 block">directions_run</span>
              <h2 className="text-2xl font-bold text-white mb-2">Follow Me</h2>
              <p className="text-white/70 mb-8">The robot will follow your AprilTag</p>
              
              <div className="bg-white/20 rounded-2xl p-4 mb-6">
                <p className="text-white/80 text-sm mb-3">Select AprilTag</p>
                <div className="flex justify-center space-x-3">
                  {([11, 12, 13] as FollowTag[]).map((tag) => (
                    <button
                      key={tag}
                      onClick={() => setSelectedTag(tag)}
                      className={`w-16 h-16 rounded-2xl font-bold text-xl transition-all ${
                        selectedTag === tag
                          ? 'bg-white text-purple-600 shadow-lg'
                          : 'bg-white/30 text-white hover:bg-white/40'
                      }`}
                    >
                      #{tag}
                    </button>
                  ))}
                </div>
              </div>

              <button onClick={handleStartFollow} className="btn-primary bg-white text-purple-600 hover:bg-white/90">
                <span className="material-icons-round mr-2 align-middle">play_arrow</span>
                Start Following
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-page-title">Follow Me Mode</h1>
        <button onClick={async () => {
          stopFollow();
          const { currentSessionId } = useRobotStore.getState();
          if (currentSessionId) {
            await api.post(`/sessions/${currentSessionId}/follow/stop`, {}).catch(() => {});
          }
        }} className="btn-danger">
          <span className="material-icons-round mr-2 align-middle">stop</span>
          Stop Following
        </button>
      </div>

      <div className="max-w-2xl mx-auto">
        <div className="robot-card-purple text-center py-12">
          <div className="absolute -right-10 -top-10 w-48 h-48 bg-white/15 rounded-full blur-3xl" />
          <div className="relative z-10">
            {/* Status Display */}
            <div className={`inline-flex items-center space-x-3 text-4xl font-bold mb-6 ${getStatusColor(follow.status)}`}>
              <span className="material-icons-round text-5xl">{getStatusIcon(follow.status)}</span>
              <span className="text-white">{follow.status}</span>
            </div>

            <div className="bg-white/20 rounded-2xl p-6 mb-6">
              <p className="text-white/70 text-sm mb-2">Tracking Tag</p>
              <p className="text-3xl font-bold text-white">#{follow.tagNumber}</p>
            </div>

            <div className="flex justify-center space-x-4">
              <button onClick={handleChangeTag} className="btn-secondary bg-white/20 border-white/30 text-white hover:bg-white/30">
                <span className="material-icons-round mr-2 align-middle">swap_horiz</span>
                Change Tag
              </button>
            </div>
          </div>
        </div>

        {/* Demo Controls */}
        <div className="robot-card-white mt-6">
          <h3 className="text-lg font-bold text-foreground mb-4">Demo: Simulate Status</h3>
          <div className="flex flex-wrap gap-2">
            <button onClick={() => simulateStatus('FOLLOWING')} className="btn-success text-sm py-2">Following</button>
            <button onClick={() => simulateStatus('LOST')} className="btn-danger text-sm py-2">Lost</button>
            <button onClick={() => simulateStatus('STOPPED')} className="btn-warning text-sm py-2">Stopped</button>
            <button onClick={() => simulateStatus('RECONNECTING')} className="btn-primary text-sm py-2">Reconnecting</button>
          </div>
        </div>
      </div>

      {/* Change Tag Dialog */}
      {showTagDialog && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center">
          <div className="bg-card rounded-2xl p-6 w-80 shadow-2xl animate-scale-in">
            <h3 className="text-lg font-bold text-foreground mb-4">Select AprilTag</h3>
            <div className="flex justify-center space-x-3 mb-6">
              {([11, 12, 13] as FollowTag[]).map((tag) => (
                <button
                  key={tag}
                  onClick={() => setSelectedTag(tag)}
                  className={`w-16 h-16 rounded-2xl font-bold text-xl transition-all ${
                    selectedTag === tag
                      ? 'bg-primary text-white shadow-lg'
                      : 'bg-slate-100 dark:bg-slate-800 text-foreground hover:bg-slate-200'
                  }`}
                >
                  #{tag}
                </button>
              ))}
            </div>
            <div className="flex space-x-3">
              <button onClick={() => setShowTagDialog(false)} className="flex-1 btn-secondary">Cancel</button>
              <button onClick={handleConfirmTagChange} className="flex-1 btn-primary">Confirm</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

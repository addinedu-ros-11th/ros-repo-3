import { useState } from 'react';
import { useAppStore } from '@/store/appStore';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet';

function generateAccessCode(): string {
  return String(Math.floor(1000 + Math.random() * 9000));
}

interface ProfileSheetProps {
  isOpen: boolean;
  onClose: () => void;
}

export function ProfileSheet({ isOpen, onClose }: ProfileSheetProps) {
  const { userName, userPhone, endSession, sessionState } = useAppStore();
  const [endStep, setEndStep] = useState<'confirm' | 'lockbox' | null>(null);
  const [accessCode, setAccessCode] = useState('');

  const isActive = sessionState === 'ACTIVE';

  const handleEndSessionStart = () => {
    setEndStep('confirm');
  };

  const handleProceedToLockbox = () => {
    setAccessCode(generateAccessCode());
    setEndStep('lockbox');
  };

  const handleConfirmAllEmpty = () => {
    endSession();
    setEndStep(null);
    onClose();
  };

  const handleCancelEnd = () => {
    setEndStep(null);
  };

  const handleLogout = () => {
    if (isActive) {
      endSession();
    }
    onClose();
  };

  return (
    <Sheet open={isOpen} onOpenChange={onClose}>
      <SheetContent side="right" className="w-[300px] sm:w-[350px]">
        <SheetHeader>
          <SheetTitle>My Profile</SheetTitle>
        </SheetHeader>

        <div className="mt-8 space-y-6">
          {/* Avatar */}
          <div className="flex flex-col items-center">
            <div className="w-24 h-24 rounded-full bg-gradient-to-br from-purple-400 to-pink-400 flex items-center justify-center text-white font-bold text-3xl shadow-lg">
              {userName.charAt(0)}
            </div>
            <h2 className="mt-4 text-xl font-bold text-foreground">{userName}</h2>
            <p className="text-sm text-muted-foreground">{userPhone}</p>
          </div>

          {/* Info Cards */}
          <div className="space-y-3">
            <div className="bg-muted rounded-xl p-4">
              <div className="flex items-center gap-3">
                <span className="material-icons-round text-primary">phone</span>
                <div>
                  <p className="text-xs text-muted-foreground">Phone Number</p>
                  <p className="font-semibold">{userPhone}</p>
                </div>
              </div>
            </div>

            <div className="bg-muted rounded-xl p-4">
              <div className="flex items-center gap-3">
                <span className="material-icons-round text-primary">history</span>
                <div>
                  <p className="text-xs text-muted-foreground">Total Sessions</p>
                  <p className="font-semibold">12 sessions</p>
                </div>
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="space-y-3 pt-4">
            <button className="w-full flex items-center gap-3 px-4 py-3 rounded-xl bg-muted hover:bg-muted/80 transition-colors active-press">
              <span className="material-icons-round text-muted-foreground">settings</span>
              <span className="font-medium">Settings</span>
            </button>

            <button className="w-full flex items-center gap-3 px-4 py-3 rounded-xl bg-muted hover:bg-muted/80 transition-colors active-press">
              <span className="material-icons-round text-muted-foreground">help</span>
              <span className="font-medium">Help & Support</span>
            </button>

            {/* End Session Button - only visible when session is active */}
            {isActive && (
              <button
                onClick={handleEndSessionStart}
                className="w-full flex items-center gap-3 px-4 py-3 rounded-xl bg-amber-500/10 hover:bg-amber-500/20 text-amber-600 transition-colors active-press"
              >
                <span className="material-icons-round">stop_circle</span>
                <span className="font-medium">End Session</span>
              </button>
            )}

            <button 
              onClick={handleLogout}
              className="w-full flex items-center gap-3 px-4 py-3 rounded-xl bg-destructive/10 hover:bg-destructive/20 text-destructive transition-colors active-press"
            >
              <span className="material-icons-round">logout</span>
              <span className="font-medium">Log Out</span>
            </button>
          </div>

          {/* App Info */}
          <div className="pt-6 text-center">
            <p className="text-xs text-muted-foreground">Mall·E v1.0.0</p>
            <p className="text-xs text-muted-foreground mt-1">© 2024 Mall·E Inc.</p>
          </div>
        </div>

        {/* End Session Step 1: Confirmation */}
        {endStep === 'confirm' && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 backdrop-blur-sm">
            <div className="bg-card rounded-3xl p-6 mx-6 max-w-sm w-full shadow-2xl space-y-4">
              <div className="flex flex-col items-center text-center space-y-3">
                <div className="w-14 h-14 rounded-full bg-amber-100 flex items-center justify-center">
                  <span className="material-icons-round text-amber-600 text-3xl">smart_toy</span>
                </div>
                <h3 className="text-lg font-bold text-foreground">End Session?</h3>
                <p className="text-sm text-muted-foreground">
                  Robot will return to Home Station. Please make sure to retrieve all items from the lockbox first.
                </p>
              </div>
              <div className="flex gap-3">
                <button
                  onClick={handleCancelEnd}
                  className="flex-1 py-3 rounded-xl border border-border text-foreground font-semibold transition-colors hover:bg-muted"
                >
                  Cancel
                </button>
                <button
                  onClick={handleProceedToLockbox}
                  className="flex-1 py-3 rounded-xl bg-amber-500 text-white font-semibold shadow-lg transition-colors hover:bg-amber-600"
                >
                  Next
                </button>
              </div>
            </div>
          </div>
        )}

        {/* End Session Step 2: Lockbox Check + Access Code */}
        {endStep === 'lockbox' && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 backdrop-blur-sm">
            <div className="bg-card rounded-3xl p-6 mx-6 max-w-sm w-full shadow-2xl space-y-5">
              <div className="flex flex-col items-center text-center space-y-3">
                <div className="w-14 h-14 rounded-full bg-blue-100 flex items-center justify-center">
                  <span className="material-icons-round text-blue-600 text-3xl">lock_open</span>
                </div>
                <h3 className="text-lg font-bold text-foreground">Check Lockbox</h3>
                <p className="text-sm text-muted-foreground">
                  Please check if all the lockboxes are empty.
                </p>
              </div>

              {/* Access Code */}
              <div className="bg-muted rounded-2xl p-5 text-center">
                <p className="text-xs font-medium text-muted-foreground mb-2">Access Code</p>
                <p className="text-3xl font-mono font-bold text-primary tracking-[0.3em]">{accessCode}</p>
                <p className="text-xs text-muted-foreground mt-2">Use this code to open the lockbox</p>
              </div>

              <button
                onClick={handleConfirmAllEmpty}
                className="w-full py-3 rounded-xl bg-primary text-primary-foreground font-semibold shadow-lg transition-colors hover:bg-primary/90"
              >
                All Empty — Confirm
              </button>
              <button
                onClick={handleCancelEnd}
                className="w-full py-2 text-sm text-muted-foreground font-medium hover:text-foreground transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}

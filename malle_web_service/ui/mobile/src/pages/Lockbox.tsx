import { useState } from 'react';
import { useAppStore, LockboxStatus } from '@/store/appStore';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';

export default function Lockbox() {
  const { lockboxSlots, lockboxLogs, openSlot, confirmSlotFull, confirmSlotEmpty } = useAppStore();
  const [selectedSlot, setSelectedSlot] = useState<number | null>(null);
  const [showToken, setShowToken] = useState(false);
  const [token, setToken] = useState('');

  const handleSlotClick = (slotNumber: number, status: LockboxStatus) => {
    if (status === 'RESERVED') return;
    setSelectedSlot(slotNumber);
  };

  const handleOpenSlot = () => {
    if (selectedSlot) {
      openSlot(selectedSlot);
      setToken(String(Math.floor(1000 + Math.random() * 9000)));
      setShowToken(true);
    }
  };

  const handleConfirmStorage = (isFull: boolean) => {
    if (selectedSlot) {
      if (isFull) {
        confirmSlotFull(selectedSlot);
      } else {
        confirmSlotEmpty(selectedSlot);
      }
    }
    setShowToken(false);
    setSelectedSlot(null);
  };

  const getSlotColor = (status: LockboxStatus) => {
    switch (status) {
      case 'FULL': return 'bg-card-dark-blue dark:bg-blue-700';
      case 'PICKED_UP': return 'bg-gradient-to-br from-emerald-500 to-teal-600 dark:from-emerald-600 dark:to-teal-700';
      case 'RESERVED': return 'bg-card-pink dark:bg-pink-600';
      case 'EMPTY': return 'bg-muted border-2 border-dashed border-muted-foreground/30';
    }
  };

  const formatLogTime = (date: Date) => {
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    return `${hours}h ago`;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-foreground">Lockbox Management</h1>
        <p className="text-muted-foreground text-sm mt-1">Manage storage slots and pickups</p>
      </div>

      {/* Slots Grid */}
      <div className="grid grid-cols-2 gap-4">
        {lockboxSlots.map((slot) => (
          <button
            key={slot.slotNumber}
            onClick={() => handleSlotClick(slot.slotNumber, slot.status)}
            className={`rounded-3xl p-5 relative overflow-hidden transition-all active-press ${getSlotColor(slot.status)} ${
              slot.status === 'RESERVED' ? 'col-span-2 ring-4 ring-pink-200 dark:ring-pink-900 shadow-lg' : ''
            } ${slot.status === 'PICKED_UP' ? 'col-span-2 ring-4 ring-emerald-200 dark:ring-emerald-900 shadow-lg' : ''
            } ${slot.status === 'EMPTY' ? 'h-44 hover:bg-muted/80 hover:border-muted-foreground/50' : ''
            } ${(slot.status === 'FULL') ? 'h-44' : ''}`}
            disabled={slot.status === 'RESERVED'}
          >
            {/* Decoration */}
            {slot.status !== 'EMPTY' && (
              <div className="card-decoration right-0 top-0 w-24 h-24 bg-white/10 -mr-6 -mt-6" />
            )}

            <div className="relative z-10 h-full flex flex-col">
              {/* Header */}
              <div className="flex justify-between items-start">
                <span className={`px-2.5 py-1 rounded-lg text-[10px] font-bold uppercase tracking-wide backdrop-blur-sm ${
                  slot.status === 'EMPTY' 
                    ? 'bg-muted-foreground/10 text-muted-foreground' 
                    : 'bg-black/20 text-white'
                }`}>
                  Slot {slot.slotNumber}
                </span>
                {slot.status === 'RESERVED' && (
                  <div className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-white animate-pulse" />
                    <span className="text-xs text-white font-medium">Selected</span>
                  </div>
                )}
                {slot.status !== 'EMPTY' && (
                  <span className="material-icons-round text-white/80">inventory_2</span>
                )}
              </div>

              {/* Content */}
              <div className="mt-auto">
                {slot.status === 'FULL' && (
                  <>
                    <p className="text-white font-bold text-xl">Full</p>
                    <p className="text-blue-100 text-xs">Occupied since {slot.occupiedSince}</p>
                  </>
                )}

                {slot.status === 'PICKED_UP' && (
                  <>
                    <h3 className="text-2xl font-bold text-white mb-2">Picked Up</h3>
                    {slot.orderInfo && (
                      <div className="flex items-center gap-2 mb-1">
                        <span className="material-icons-round text-white/90 text-lg">local_shipping</span>
                        <span className="text-sm font-medium text-white/90">
                          Order {slot.orderInfo.orderId} • {slot.orderInfo.storeName}
                        </span>
                      </div>
                    )}
                    <p className="text-xs text-white/70">Items loaded since {slot.occupiedSince}</p>
                  </>
                )}

                {slot.status === 'RESERVED' && slot.orderInfo && (
                  <>
                    <h3 className="text-2xl font-bold text-white mb-2">Reserved for Pickup</h3>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="material-icons-round text-white/90 text-lg">shopping_bag</span>
                      <span className="text-sm font-medium text-white/90">
                        Order {slot.orderInfo.orderId} • {slot.orderInfo.storeName}
                      </span>
                    </div>
                    <p className="text-xs text-white/70 mb-4">
                      Ready for collection by {slot.orderInfo.customerName}
                    </p>
                  </>
                )}

                {slot.status === 'EMPTY' && (
                  <div className="flex flex-col items-center justify-center h-full">
                    <span className="material-icons-round text-3xl text-muted-foreground mb-2">add_circle_outline</span>
                    <p className="font-semibold text-sm text-muted-foreground">Slot {slot.slotNumber} Empty</p>
                  </div>
                )}
              </div>
            </div>
          </button>
        ))}
      </div>

      {/* Recent Logs */}
      <div>
        <h3 className="text-lg font-bold flex items-center gap-2 mb-3">
          <span className="material-icons-round text-muted-foreground">history</span>
          Recent Logs
        </h3>
        <div className="bg-card rounded-2xl border border-border divide-y divide-border overflow-hidden">
          {lockboxLogs.slice(0, 5).map((log) => (
            <div key={log.id} className="px-4 py-3 flex items-center gap-3">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                log.result === 'SUCCESS' 
                  ? log.action === 'SECURED' ? 'bg-emerald-100 dark:bg-emerald-900/50' : 'bg-blue-100 dark:bg-blue-900/50'
                  : 'bg-red-100 dark:bg-red-900/50'
              }`}>
                <span className={`material-icons-round text-sm ${
                  log.result === 'SUCCESS'
                    ? log.action === 'SECURED' ? 'text-emerald-600' : 'text-blue-600'
                    : 'text-red-600'
                }`}>
                  {log.action === 'SECURED' ? 'lock' : log.action === 'OPENED' ? 'lock_open' : 'error'}
                </span>
              </div>
              <div className="flex-1">
                <p className="text-sm font-semibold text-foreground">Slot {log.slotNumber} {log.action.toLowerCase()}</p>
                <p className="text-xs text-muted-foreground">{log.description}</p>
              </div>
              <span className="text-xs font-mono text-muted-foreground">{formatLogTime(log.timestamp)}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Confirm Dialog */}
      <Dialog open={selectedSlot !== null && !showToken} onOpenChange={() => setSelectedSlot(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Open Slot {selectedSlot}?</DialogTitle>
          </DialogHeader>
          <p className="text-muted-foreground text-sm">
            This will unlock the lockbox slot. You'll receive a one-time access code.
          </p>
          <DialogFooter className="flex gap-3">
            <button 
              onClick={() => setSelectedSlot(null)}
              className="flex-1 py-3 rounded-xl border border-border font-semibold active-press-sm"
            >
              Cancel
            </button>
            <button 
              onClick={handleOpenSlot}
              className="flex-1 py-3 rounded-xl bg-primary text-primary-foreground font-semibold shadow-md active-press-sm"
            >
              Open Slot
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Token Overlay */}
      <Dialog open={showToken} onOpenChange={() => {}}>
        <DialogContent className="max-w-[320px]">
          <div className="text-center py-4">
            <div className="w-20 h-20 rounded-full bg-primary/10 mx-auto flex items-center justify-center mb-4">
              <span className="material-icons-round text-primary text-4xl">vpn_key</span>
            </div>
            <h2 className="text-xl font-bold mb-2">Access Code</h2>
            <p className="text-muted-foreground text-sm mb-4">Enter this code on the lockbox keypad</p>
            <div className="bg-muted rounded-2xl py-4 px-6 mb-6">
              <span className="text-3xl font-mono font-bold tracking-widest text-foreground">{token}</span>
            </div>
            <p className="text-xs text-muted-foreground mb-6">Did you store items in the box?</p>
            <div className="flex gap-3">
              <button
                onClick={() => handleConfirmStorage(false)}
                className="flex-1 py-3 rounded-xl border border-border font-semibold active-press-sm"
              >
                No, Empty
              </button>
              <button
                onClick={() => handleConfirmStorage(true)}
                className="flex-1 py-3 rounded-xl bg-primary text-primary-foreground font-semibold active-press-sm"
              >
                Yes, Stored
              </button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

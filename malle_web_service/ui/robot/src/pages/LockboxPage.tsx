import { useRobotStore } from '@/stores/robotStore';
import { useState, useEffect } from 'react';
import type { LockboxSlot } from '@/types/robot';

export function LockboxPage() {
  const { lockboxSlots, lockboxLogs, openSlot, updateSlotStatus, addLockboxLog, pendingLockboxSlot, setPendingLockboxSlot, initLockboxSlots } = useRobotStore();
  const [selectedSlot, setSelectedSlot] = useState<LockboxSlot | null>(null);
  const [showOpenDialog, setShowOpenDialog] = useState(false);
  const [showTokenDialog, setShowTokenDialog] = useState(false);
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [token, setToken] = useState('');
  const [tokenError, setTokenError] = useState(false);

  // 마운트 시 서버에서 실제 슬롯 상태 로드
  // useEffect(() => {
  //   initLockboxSlots();
  // }, []);

  // Check for pending lockbox slot from voice command
  useEffect(() => {
    if (pendingLockboxSlot) {
      const slot = lockboxSlots.find(s => s.number === pendingLockboxSlot);
      if (slot && slot.status !== 'RESERVED') {
        setSelectedSlot(slot);
        setShowOpenDialog(true);
      }
      setPendingLockboxSlot(null);
    }
  }, [pendingLockboxSlot]);

  const handleSlotClick = (slot: LockboxSlot) => {
    if (slot.status === 'RESERVED') return;
    setSelectedSlot(slot);
    setShowOpenDialog(true);
  };

  const handleOpenSlot = () => {
    setShowOpenDialog(false);
    setShowTokenDialog(true);
  };

  const handleTokenKeyPress = (digit: string) => {
    if (token.length < 4) {
      setToken(prev => prev + digit);
      setTokenError(false);
    }
  };

  const handleTokenBackspace = () => {
    setToken(prev => prev.slice(0, -1));
    setTokenError(false);
  };

  const handleTokenConfirm = () => {
    if (token.length === 4 && selectedSlot) {
      // Demo: Accept any 4-digit token
      openSlot(selectedSlot.number);
      setShowTokenDialog(false);
      setToken('');
      
      // Simulate door close after delay
      setTimeout(() => {
        setShowConfirmDialog(true);
      }, 1500);
    } else {
      setTokenError(true);
    }
  };

  const handleConfirmStorage = (stored: boolean) => {
    if (selectedSlot) {
      if (stored) {
        updateSlotStatus(selectedSlot.number, 'FULL');
        addLockboxLog({
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          slotNumber: selectedSlot.number,
          action: 'SECURED',
          result: 'SUCCESS',
          description: `Slot ${selectedSlot.number} secured with items`,
        });
      } else {
        updateSlotStatus(selectedSlot.number, 'EMPTY');
        addLockboxLog({
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          slotNumber: selectedSlot.number,
          action: 'SECURED',
          result: 'SUCCESS',
          description: `Slot ${selectedSlot.number} remains empty`,
        });
      }
    }
    setShowConfirmDialog(false);
    setSelectedSlot(null);
  };

  return (
    <div>
      <h1 className="text-page-title mb-8">Lockbox Management</h1>

      {/* Slot Grid */}
      <div className="grid grid-cols-5 gap-4 mb-8">
        {lockboxSlots.map((slot) => (
          <button
            key={slot.number}
            onClick={() => handleSlotClick(slot)}
            disabled={slot.status === 'RESERVED'}
            className={`h-52 ${
              slot.status === 'FULL' && slot.isPickupOrder
                ? 'slot-pickup'
                : slot.status === 'FULL'
                ? 'slot-full'
                : slot.status === 'RESERVED'
                ? 'slot-reserved'
                : 'slot-empty'
            }`}
          >
            <div className="absolute -right-4 -top-4 w-24 h-24 bg-white/10 rounded-full blur-2xl" />
            <div className="relative z-10 h-full flex flex-col">
              <span className={`self-start px-2 py-1 rounded-lg text-[10px] font-bold uppercase backdrop-blur-sm ${
                slot.status === 'EMPTY' ? 'bg-slate-200 text-slate-600' : 'bg-black/20 text-white'
              }`}>
                Slot {slot.number}
              </span>

              <div className="flex-1 flex flex-col items-center justify-center">
                <span className={`material-icons-round text-3xl mb-2 ${
                  slot.status === 'EMPTY' ? 'text-slate-400' : 'text-white/80'
                }`}>
                  {slot.status === 'EMPTY' ? 'add_circle_outline' : slot.status === 'RESERVED' ? 'shopping_bag' : 'inventory_2'}
                </span>
                <span className={`text-xl font-bold ${slot.status === 'EMPTY' ? 'text-slate-500' : 'text-white'}`}>
                  {slot.status === 'FULL' && slot.pickedUp ? 'Picked up' : slot.status === 'FULL' ? 'Full' : slot.status === 'RESERVED' ? 'Reserved' : 'Empty'}
                </span>
                {slot.status === 'FULL' && slot.isPickupOrder && slot.orderInfo && (
                  // <div className="mt-1 text-center">
                  //   <span className="text-[10px] text-white/70 block">{slot.orderInfo.orderId}</span>
                  //   <span className="text-[10px] text-white/70 block">{slot.orderInfo.storeName}</span>
                  // </div>
                  <span className="text-xs text-white/70 mt-1">
                    {slot.orderInfo.orderId} • {slot.orderInfo.storeName}
                  </span>
                )}
                {slot.status === 'FULL' && !slot.isPickupOrder && slot.occupiedSince && (
                  <span className="text-xs text-white/70 mt-1">Since {slot.occupiedSince}</span>
                )}
                {slot.status === 'RESERVED' && slot.orderInfo && (
                  <span className="text-xs text-white/70 mt-1">
                    {slot.orderInfo.orderId} • {slot.orderInfo.storeName}
                  </span>
                )}
              </div>

              {(slot.status === 'FULL' || slot.status === 'EMPTY') && (
                <div className="space-y-2">
                  <button className={`w-full py-2 rounded-xl text-sm font-bold transition-all ${
                    slot.status === 'EMPTY' 
                      ? 'bg-slate-300 text-slate-700 hover:bg-slate-400' 
                      : 'bg-white/20 text-white hover:bg-white/30'
                  }`}>
                    <span className="material-icons-round text-sm mr-1 align-middle">lock_open</span>
                    Open
                  </button>
                </div>
              )}
            </div>
          </button>
        ))}
      </div>

      {/* Recent Logs */}
      <div className="robot-card-white">
        <h3 className="text-lg font-bold text-foreground mb-4">Recent Activity</h3>
        <div className="divide-y divide-slate-100 dark:divide-slate-800">
          {lockboxLogs.slice(0, 5).map((log) => (
            <div key={log.id} className="py-3 flex items-center space-x-4">
              <div className={log.result === 'SUCCESS' ? 'log-icon-success' : 'log-icon-fail'}>
                <span className="material-icons-round text-sm">
                  {log.action === 'OPENED' ? 'lock_open' : log.action === 'SECURED' ? 'lock' : 'error'}
                </span>
              </div>
              <div className="flex-1">
                <p className="font-medium text-foreground">{log.description}</p>
                <p className="text-sm text-muted-foreground">Slot {log.slotNumber}</p>
              </div>
              <span className="text-xs font-mono text-muted-foreground">{log.timestamp}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Open Confirmation Dialog */}
      {showOpenDialog && selectedSlot && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center">
          <div className="bg-card rounded-2xl p-6 w-80 shadow-2xl animate-scale-in">
            <h3 className="text-lg font-bold text-foreground mb-2">Open Slot {selectedSlot.number}?</h3>
            <p className="text-muted-foreground mb-6">This will unlock the lockbox compartment.</p>
            <div className="flex space-x-3">
              <button onClick={() => setShowOpenDialog(false)} className="flex-1 btn-secondary">Cancel</button>
              <button onClick={handleOpenSlot} className="flex-1 btn-primary">Open</button>
            </div>
          </div>
        </div>
      )}

      {/* Token Entry Dialog */}
      {showTokenDialog && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center">
          <div className={`bg-card rounded-2xl p-6 w-96 shadow-2xl ${tokenError ? 'animate-shake' : 'animate-scale-in'}`}>
            <h3 className="text-lg font-bold text-foreground mb-2 text-center">Enter Access Token</h3>
            <p className="text-muted-foreground mb-6 text-center text-sm">Slot {selectedSlot?.number}</p>

            {/* Token Display */}
            <div className="flex justify-center space-x-3 mb-6">
              {[0, 1, 2, 3].map((index) => (
                <div key={index} className={token.length > index ? 'pin-box-filled' : 'pin-box'}>
                  {token[index] ? '•' : ''}
                </div>
              ))}
            </div>

            {tokenError && (
              <p className="text-destructive text-sm font-medium text-center mb-4">Invalid token</p>
            )}

            {/* Numeric Keypad */}
            <div className="grid grid-cols-3 gap-3 max-w-xs mx-auto mb-6">
              {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((digit) => (
                <button key={digit} onClick={() => handleTokenKeyPress(String(digit))} className="keypad-btn">
                  {digit}
                </button>
              ))}
              <div />
              <button onClick={() => handleTokenKeyPress('0')} className="keypad-btn">0</button>
              <button onClick={handleTokenBackspace} className="keypad-btn">
                <span className="material-icons-round">backspace</span>
              </button>
            </div>

            <div className="flex space-x-3">
              <button onClick={() => { setShowTokenDialog(false); setToken(''); }} className="flex-1 btn-secondary">Cancel</button>
              <button onClick={handleTokenConfirm} disabled={token.length !== 4} className="flex-1 btn-primary disabled:opacity-50">
                Unlock
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Storage Confirmation Dialog */}
      {showConfirmDialog && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center">
          <div className="bg-card rounded-2xl p-6 w-80 shadow-2xl animate-scale-in">
            <div className="text-center mb-6">
              <div className="w-16 h-16 mx-auto rounded-full bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center mb-4">
                <span className="material-icons-round text-emerald-500 text-3xl">lock_open</span>
              </div>
              <h3 className="text-lg font-bold text-foreground">Slot {selectedSlot?.number} Open</h3>
              <p className="text-muted-foreground text-sm mt-2">Door has been closed. Did you store items?</p>
            </div>
            <div className="flex space-x-3">
              <button onClick={() => handleConfirmStorage(false)} className="flex-1 btn-secondary">No</button>
              <button onClick={() => handleConfirmStorage(true)} className="flex-1 btn-success">Yes, Stored</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

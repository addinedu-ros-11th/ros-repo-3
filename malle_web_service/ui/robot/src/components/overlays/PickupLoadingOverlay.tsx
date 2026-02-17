import { useState, useEffect } from 'react';
import { useRobotStore } from '@/stores/robotStore';

type LoadingStep = 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8;

const steps = [
  { id: 1, label: 'Moving to pickup location', icon: 'directions' },
  { id: 2, label: 'Arrived at store', icon: 'place' },
  { id: 3, label: 'Staff PIN entry', icon: 'pin' },
  { id: 4, label: 'Loading items', icon: 'inventory_2' },
  { id: 5, label: 'Confirming load', icon: 'fact_check' },
  { id: 6, label: 'Requesting meet-up point', icon: 'share_location' },
  { id: 7, label: 'Heading to meet-up', icon: 'directions_walk' },
  { id: 8, label: 'Complete', icon: 'check_circle' },
];

export function PickupLoadingOverlay() {
  const { pickup, setShowLoadingOverlay, completePickup, setPickupStatus } = useRobotStore();
  const [currentStep, setCurrentStep] = useState<LoadingStep>(1);
  const [staffPin, setStaffPin] = useState('');
  const [pinError, setPinError] = useState(false);

  useEffect(() => {
    if (pickup.showLoadingOverlay && currentStep === 1) {
      // Simulate moving to pickup location
      const timer = setTimeout(() => {
        setCurrentStep(2);
        setPickupStatus('ARRIVED');
      }, 2000);
      return () => clearTimeout(timer);
    }
  }, [pickup.showLoadingOverlay, currentStep, setPickupStatus]);

  const handleStaffPinKeyPress = (digit: string) => {
    if (staffPin.length < 4) {
      setStaffPin(prev => prev + digit);
      setPinError(false);
    }
  };

  const handleStaffPinBackspace = () => {
    setStaffPin(prev => prev.slice(0, -1));
    setPinError(false);
  };

  const handleStaffPinConfirm = () => {
    if (staffPin.length === 4) {
      // Demo: Accept any 4-digit PIN
      setCurrentStep(4);
      setPickupStatus('LOADING');
      setStaffPin('');
      // Simulate loading time
      setTimeout(() => setCurrentStep(5), 2000);
    }
  };

  const handleConfirmLoad = (loaded: boolean) => {
    if (loaded) {
      setCurrentStep(6);
      setPickupStatus('LOADED');
    } else {
      setCurrentStep(3);
      setPickupStatus('STAFF_PIN');
    }
  };

  const handleMeetUpReceived = () => {
    setCurrentStep(7);
    setTimeout(() => setCurrentStep(8), 2500);
    setTimeout(() => {
      completePickup();
      setShowLoadingOverlay(false);
      setCurrentStep(1);
    }, 5000);
  };

  if (!pickup.showLoadingOverlay || !pickup.currentOrder) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center">
      <div className="bg-card rounded-3xl p-8 w-[600px] max-w-[90vw] shadow-2xl">
        {/* Stepper */}
        <div className="flex items-center justify-center mb-8">
          {steps.map((step, index) => (
            <div key={step.id} className="flex items-center">
              <div
                className={
                  currentStep > step.id
                    ? 'stepper-dot-complete'
                    : currentStep === step.id
                    ? 'stepper-dot-current'
                    : 'stepper-dot-pending'
                }
              />
              {index < steps.length - 1 && (
                <div
                  className={currentStep > step.id ? 'stepper-line-complete w-8' : 'stepper-line w-8'}
                />
              )}
            </div>
          ))}
        </div>

        {/* Step Content */}
        <div className="text-center">
          {currentStep === 1 && (
            <div className="py-8">
              <div className="w-16 h-16 mx-auto rounded-full bg-primary/10 flex items-center justify-center mb-4 animate-pulse">
                <span className="material-icons-round text-primary text-3xl">directions</span>
              </div>
              <h3 className="text-xl font-bold text-foreground">Moving to pickup location...</h3>
              <p className="text-muted-foreground mt-2">{pickup.currentOrder.storeName}</p>
            </div>
          )}

          {currentStep === 2 && (
            <div className="py-8">
              <div className="w-16 h-16 mx-auto rounded-full bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center mb-4">
                <span className="material-icons-round text-emerald-500 text-3xl">place</span>
              </div>
              <h3 className="text-xl font-bold text-foreground">Arrived at {pickup.currentOrder.storeName}</h3>
              <div className="bg-muted rounded-2xl p-4 mt-4 inline-block">
                <p className="text-sm font-medium">
                  Order {pickup.currentOrder.orderId} • Slot {pickup.currentOrder.slotId} (RESERVED)
                </p>
              </div>
              <button
                onClick={() => setCurrentStep(3)}
                className="btn-primary mt-6"
              >
                Proceed to PIN Entry
              </button>
            </div>
          )}

          {currentStep === 3 && (
            <div className="py-4">
              <h3 className="text-xl font-bold text-foreground mb-2">Staff: Enter PIN to open lockbox</h3>
              <p className="text-sm text-muted-foreground mb-6">Slot {pickup.currentOrder.slotId}</p>

              {/* PIN Display */}
              <div className="flex justify-center space-x-3 mb-6">
                {[0, 1, 2, 3].map((index) => (
                  <div
                    key={index}
                    className={staffPin.length > index ? 'pin-box-filled' : 'pin-box'}
                  >
                    {staffPin[index] ? '•' : ''}
                  </div>
                ))}
              </div>

              {pinError && (
                <p className="text-destructive text-sm font-medium mb-4">Invalid PIN</p>
              )}

              {/* Numeric Keypad */}
              <div className="grid grid-cols-3 gap-3 max-w-xs mx-auto mb-6">
                {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((digit) => (
                  <button
                    key={digit}
                    onClick={() => handleStaffPinKeyPress(String(digit))}
                    className="keypad-btn"
                  >
                    {digit}
                  </button>
                ))}
                <div />
                <button onClick={() => handleStaffPinKeyPress('0')} className="keypad-btn">0</button>
                <button onClick={handleStaffPinBackspace} className="keypad-btn">
                  <span className="material-icons-round">backspace</span>
                </button>
              </div>

              <button
                onClick={handleStaffPinConfirm}
                disabled={staffPin.length !== 4}
                className="btn-primary disabled:opacity-50"
              >
                Open Slot
              </button>
            </div>
          )}

          {currentStep === 4 && (
            <div className="py-8">
              <div className="w-16 h-16 mx-auto rounded-full bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center mb-4 animate-pulse">
                <span className="material-icons-round text-amber-500 text-3xl">inventory_2</span>
              </div>
              <h3 className="text-xl font-bold text-foreground">Slot {pickup.currentOrder.slotId} is OPEN</h3>
              <p className="text-muted-foreground mt-2">Please load items</p>
              <p className="text-sm text-muted-foreground mt-4">Staff closes the door when done</p>
            </div>
          )}

          {currentStep === 5 && (
            <div className="py-8">
              <div className="w-16 h-16 mx-auto rounded-full bg-primary/10 flex items-center justify-center mb-4">
                <span className="material-icons-round text-primary text-3xl">fact_check</span>
              </div>
              <h3 className="text-xl font-bold text-foreground">Loading complete?</h3>
              <div className="flex justify-center space-x-4 mt-6">
                <button onClick={() => handleConfirmLoad(false)} className="btn-secondary">
                  No, Retry
                </button>
                <button onClick={() => handleConfirmLoad(true)} className="btn-success">
                  Yes, Loaded
                </button>
              </div>
            </div>
          )}

          {currentStep === 6 && (
            <div className="py-8">
              <div className="w-16 h-16 mx-auto rounded-full bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center mb-4 animate-pulse">
                <span className="material-icons-round text-amber-500 text-3xl">share_location</span>
              </div>
              <h3 className="text-xl font-bold text-foreground">Asking for meet-up point</h3>
              <p className="text-muted-foreground mt-2">Waiting for customer to set a meet-up location...</p>
              <div className="bg-muted rounded-2xl p-4 mt-4 inline-block">
                <p className="text-sm font-medium">📲 Request sent to customer app</p>
              </div>
              <button
                onClick={handleMeetUpReceived}
                className="btn-primary mt-6"
              >
                Simulate: Location Received
              </button>
            </div>
          )}

          {currentStep === 7 && (
            <div className="py-8">
              <div className="w-16 h-16 mx-auto rounded-full bg-primary/10 flex items-center justify-center mb-4 animate-pulse">
                <span className="material-icons-round text-primary text-3xl">directions_walk</span>
              </div>
              <h3 className="text-xl font-bold text-foreground">Heading to meet-up area...</h3>
              <p className="text-muted-foreground mt-2">Meet-up point received!</p>
            </div>
          )}

          {currentStep === 8 && (
            <div className="py-8">
              <div className="w-16 h-16 mx-auto rounded-full bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center mb-4">
                <span className="material-icons-round text-emerald-500 text-3xl">check_circle</span>
              </div>
              <h3 className="text-xl font-bold text-foreground">Successfully returned!</h3>
              <p className="text-muted-foreground mt-2">Items delivered to meet-up point.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

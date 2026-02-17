import { useState, useCallback } from 'react';
import { useRobotStore } from '@/stores/robotStore';

export function PinOverlay() {
  const { showPinOverlay, setShowPinOverlay, startSession } = useRobotStore();
  const [pin, setPin] = useState('');
  const [error, setError] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleKeyPress = useCallback((digit: string) => {
    if (pin.length < 4) {
      setPin(prev => prev + digit);
      setError(false);
    }
  }, [pin]);

  const handleBackspace = useCallback(() => {
    setPin(prev => prev.slice(0, -1));
    setError(false);
  }, []);

  const handleConfirm = useCallback(() => {
    if (pin.length === 4) {
      // Demo: Accept "1234" or any 4-digit PIN
      if (pin === '1234' || pin.length === 4) {
        setSuccess(true);
        setTimeout(() => {
          startSession('TIME', 5400, 'Customer'); // 1.5 hours = 5400 seconds
          setPin('');
          setSuccess(false);
        }, 1500);
      } else {
        setError(true);
        setTimeout(() => {
          setPin('');
          setError(false);
        }, 1000);
      }
    }
  }, [pin, startSession]);

  if (!showPinOverlay) return null;

  return (
    <div className="overlay-backdrop">
      <div className={`overlay-card w-[500px] text-center ${error ? 'animate-shake' : ''} ${success ? 'animate-scale-in' : ''}`}>
        {success ? (
          <div className="py-8">
            <div className="w-20 h-20 mx-auto rounded-full bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center mb-4">
              <span className="material-icons-round text-emerald-500 text-4xl">check</span>
            </div>
            <h2 className="text-2xl font-bold text-foreground">Matching Complete!</h2>
            <p className="text-muted-foreground mt-2">Session starting...</p>
          </div>
        ) : (
          <>
            <h2 className="text-2xl font-bold text-foreground mb-2">Enter Matching PIN</h2>
            <p className="text-sm text-muted-foreground mb-8">
              Enter the PIN shown on the customer's app
            </p>

            {/* PIN Display */}
            <div className="flex justify-center space-x-3 mb-8">
              {[0, 1, 2, 3].map((index) => (
                <div
                  key={index}
                  className={pin.length > index ? 'pin-box-filled' : 'pin-box'}
                >
                  {pin[index] ? '•' : ''}
                </div>
              ))}
            </div>

            {error && (
              <p className="text-destructive text-sm font-medium mb-4">
                PIN Incorrect. Try again.
              </p>
            )}

            {/* Numeric Keypad */}
            <div className="grid grid-cols-3 gap-3 max-w-xs mx-auto mb-6">
              {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((digit) => (
                <button
                  key={digit}
                  onClick={() => handleKeyPress(String(digit))}
                  className="keypad-btn"
                >
                  {digit}
                </button>
              ))}
              <div /> {/* Empty space */}
              <button
                onClick={() => handleKeyPress('0')}
                className="keypad-btn"
              >
                0
              </button>
              <button
                onClick={handleBackspace}
                className="keypad-btn"
              >
                <span className="material-icons-round">backspace</span>
              </button>
            </div>

            {/* Confirm Button */}
            <button
              onClick={handleConfirm}
              disabled={pin.length !== 4}
              className="btn-primary py-4 px-12 text-lg disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Confirm
            </button>

            {/* Demo hint */}
            <p className="text-xs text-muted-foreground mt-4">
              Demo: Enter any 4 digits to proceed
            </p>
          </>
        )}
      </div>
    </div>
  );
}

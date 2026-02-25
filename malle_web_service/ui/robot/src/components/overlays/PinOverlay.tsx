import { useState, useCallback } from 'react';
import { useRobotStore } from '@/stores/robotStore';
import { sessionApi } from '@/api/sessions';

export function PinOverlay() {
  const { showPinOverlay, currentSessionId, startSession } = useRobotStore();
  const [pin, setPin] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleKeyPress = useCallback((digit: string) => {
    if (loading) return;
    if (pin.length < 4) {
      setPin(prev => prev + digit);
      setError(null);
    }
  }, [pin, loading]);

  const handleBackspace = useCallback(() => {
    if (loading) return;
    setPin(prev => prev.slice(0, -1));
    setError(null);
  }, [loading]);

  const handleConfirm = useCallback(async () => {
    if (pin.length !== 4 || loading) return;

    setLoading(true);
    setError(null);

    // 데모 모드: currentSessionId 없으면 PIN 검증 없이 바로 세션 활성화
    if (!currentSessionId) {
      setSuccess(true);
      setTimeout(() => {
        startSession('TIME', 7200, 'Demo Customer');
        setPin('');
        setSuccess(false);
      }, 1000);
      setLoading(false);
      return;
    }

    try {
      // 실제 세션: 서버 PIN 검증 → 성공 시 WS SESSION_ACTIVE 이벤트 → startSession() 자동 호출
      await sessionApi.verifyPin(currentSessionId, pin);
      setSuccess(true);
      // WS가 늦게 오는 경우 대비 1.5초 fallback
      setTimeout(() => {
        const state = useRobotStore.getState();
        if (state.sessionState !== 'ACTIVE') {
          startSession('TIME', 7200, 'Customer');
        }
        setPin('');
        setSuccess(false);
      }, 1500);
    } catch (e: any) {
      const msg = e?.response?.data?.detail ?? 'Invalid PIN';
      setError(msg);
      setTimeout(() => {
        setPin('');
        setError(null);
      }, 1200);
    } finally {
      setLoading(false);
    }
  }, [pin, currentSessionId, loading, startSession]);

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
                {error}
              </p>
            )}

            {/* Numeric Keypad */}
            <div className="grid grid-cols-3 gap-3 max-w-xs mx-auto mb-6">
              {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((digit) => (
                <button
                  key={digit}
                  onClick={() => handleKeyPress(String(digit))}
                  disabled={loading}
                  className="keypad-btn disabled:opacity-50"
                >
                  {digit}
                </button>
              ))}
              <div />
              <button
                onClick={() => handleKeyPress('0')}
                disabled={loading}
                className="keypad-btn disabled:opacity-50"
              >
                0
              </button>
              <button
                onClick={handleBackspace}
                disabled={loading}
                className="keypad-btn disabled:opacity-50"
              >
                <span className="material-icons-round">backspace</span>
              </button>
            </div>

            {/* Confirm Button */}
            <button
              onClick={handleConfirm}
              disabled={pin.length !== 4 || loading}
              className="btn-primary py-4 px-12 text-lg disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 mx-auto"
            >
              {loading && <span className="material-icons-round text-sm animate-spin">refresh</span>}
              Confirm
            </button>
          </>
        )}
      </div>
    </div>
  );
}
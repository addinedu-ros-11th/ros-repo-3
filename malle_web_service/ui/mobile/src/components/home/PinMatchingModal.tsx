import { useState, useEffect } from 'react';
import { useAppStore } from '@/store/appStore';

interface PinMatchingModalProps {
  isOpen: boolean;
}

function generatePin(): string {
  return String(Math.floor(1000 + Math.random() * 9000));
}

export function PinMatchingModal({ isOpen }: PinMatchingModalProps) {
  const { activateSession, robot } = useAppStore();
  const [pin, setPin] = useState('');

  useEffect(() => {
    if (isOpen) setPin(generatePin());
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-gradient-to-br from-primary to-blue-700 flex flex-col items-center justify-center px-8">
      {/* Robot Info */}
      <div className="mb-8 text-center">
        <div className="w-20 h-20 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center mx-auto mb-4">
          <span className="material-icons-round text-white text-4xl">smart_toy</span>
        </div>
        <h2 className="text-white text-2xl font-bold">{robot?.name}</h2>
        <p className="text-white/70 mt-3">Enter this PIN on the robot screen</p>
      </div>

      {/* PIN Display */}
      <div className="flex gap-4 mb-10">
        {pin.split('').map((digit, i) => (
          <div
            key={i}
            className="w-16 h-20 rounded-2xl bg-white flex items-center justify-center"
          >
            <span className="text-primary text-4xl font-bold">{digit}</span>
          </div>
        ))}
      </div>

      {/* Next Button */}
      <button
        onClick={activateSession}
        className="w-full max-w-[280px] h-14 rounded-2xl bg-white text-primary font-bold text-lg active-press-sm transition-all"
      >
        Next
      </button>
      <p className="text-white/50 text-xs mt-4 text-center">
        Demo: In production, session starts automatically after PIN verification on the robot.
      </p>
    </div>
  );
}

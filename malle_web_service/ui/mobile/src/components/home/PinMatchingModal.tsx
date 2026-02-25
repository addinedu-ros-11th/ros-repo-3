import { useAppStore } from '@/store/appStore';

interface PinMatchingModalProps {
  isOpen: boolean;
}

export function PinMatchingModal({ isOpen }: PinMatchingModalProps) {
  const { activateSession, robot, matchPin } = useAppStore();

  if (!isOpen) return null;

  // 서버에서 받은 match_pin을 표시 (WS PIN_MATCHING 또는 세션 생성 REST 응답에서 저장됨)
  // matchPin이 없으면 로딩 표시
  const digits = matchPin ? matchPin.split('') : ['·', '·', '·', '·'];

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

      {/* PIN Display — 서버에서 받은 match_pin */}
      <div className="flex gap-4 mb-10">
        {digits.map((digit, i) => (
          <div
            key={i}
            className="w-16 h-20 rounded-2xl bg-white flex items-center justify-center"
          >
            <span className="text-primary text-4xl font-bold">{digit}</span>
          </div>
        ))}
      </div>

      {!matchPin && (
        <p className="text-white/60 text-sm mb-6 animate-pulse">Waiting for PIN...</p>
      )}

      {/* 데모용 수동 활성화 버튼 — 실제로는 로봇 PIN 입력 성공 시 WS SESSION_ACTIVE로 자동 활성화 */}
      <button
        onClick={activateSession}
        disabled={!matchPin}
        className="w-full max-w-[280px] h-14 rounded-2xl bg-white text-primary font-bold text-lg active-press-sm transition-all disabled:opacity-40"
      >
        Next (Demo)
      </button>
      <p className="text-white/50 text-xs mt-4 text-center">
        Session activates automatically when the robot confirms the PIN.
      </p>
    </div>
  );
}
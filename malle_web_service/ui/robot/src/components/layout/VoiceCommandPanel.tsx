import { useState, useEffect, useCallback } from 'react';
import { useRobotStore } from '@/stores/robotStore';
import { useNavigate } from 'react-router-dom';
import { parseVoiceCommand } from '@/lib/voiceParser';
import type { VoiceIntentResult } from '@/types/robot';

interface VoiceCommandPanelProps {
  open: boolean;
  onClose: () => void;
}

type VoiceState = 'idle' | 'listening' | 'processing' | 'done';

const quickCommands = [
  'Guide me to Zara',
  'Open lockbox slot 3',
  'Start follow mode with tag 12',
  'Create pickup order from Nike',
  'Show robot status',
  'Return to station',
  'Emergency stop',
];

export function VoiceCommandPanel({ open, onClose }: VoiceCommandPanelProps) {
  const [voiceState, setVoiceState] = useState<VoiceState>('idle');
  const [transcript, setTranscript] = useState('');
  const [result, setResult] = useState<VoiceIntentResult | null>(null);
  const navigate = useNavigate();
  const { addNotification, executeVoiceIntent } = useRobotStore();

  const reset = useCallback(() => {
    setVoiceState('idle');
    setTranscript('');
    setResult(null);
  }, []);

  useEffect(() => {
    if (!open) reset();
  }, [open, reset]);

  const processCommand = (command: string) => {
    setTranscript(command);
    setVoiceState('processing');

    setTimeout(() => {
      const intent = parseVoiceCommand(command);
      const res = executeVoiceIntent(intent);
      setResult(res);
      setVoiceState('done');
    }, 800);
  };

  const handleMicTap = () => {
    if (voiceState === 'listening' || voiceState === 'processing') return;

    reset();
    setVoiceState('listening');

    // Mock: after 2s show hardcoded transcript
    setTimeout(() => {
      processCommand('Guide me to Nike store');
    }, 2000);
  };

  const handleChipTap = (command: string) => {
    reset();
    processCommand(command);
  };

  const handleExecute = () => {
    if (result?.navigateTo) {
      navigate(result.navigateTo);
    }
    addNotification({
      category: 'SYSTEM',
      title: 'Voice Command',
      description: transcript,
    });
    onClose();
  };

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/20 z-[44]" onClick={onClose} />

      {/* Panel */}
      <div className="fixed top-14 right-0 bottom-0 w-[420px] z-[45] bg-card dark:bg-card border-l border-border shadow-2xl transform transition-transform duration-300 flex flex-col">
        {/* Header */}
        <div className="px-6 py-5 border-b border-border flex items-center justify-between shrink-0">
          <h2 className="text-xl font-bold text-foreground">Voice Command</h2>
          <button onClick={onClose} className="p-2 rounded-full hover:bg-muted transition-colors">
            <span className="material-icons-round text-muted-foreground">close</span>
          </button>
        </div>

        {/* Listening Area */}
        <div className="px-6 py-10 flex flex-col items-center shrink-0">
          <button
            onClick={handleMicTap}
            className="w-24 h-24 rounded-full bg-primary/10 flex items-center justify-center cursor-pointer active:scale-95 transition-all relative"
          >
            {voiceState === 'listening' && (
              <>
                <span className="absolute inset-0 rounded-full ring-[6px] ring-primary/20 animate-ping" />
                <span className="absolute inset-[-8px] rounded-full ring-[6px] ring-primary/10 animate-ping" style={{ animationDelay: '0.3s' }} />
                <span className="absolute inset-[-16px] rounded-full ring-[6px] ring-primary/5 animate-ping" style={{ animationDelay: '0.6s' }} />
              </>
            )}
            {voiceState === 'processing' ? (
              <span className="material-icons-round text-primary text-4xl animate-spin">sync</span>
            ) : (
              <span className="material-icons-round text-primary text-4xl">mic</span>
            )}
          </button>

          <p className={`mt-4 text-sm ${
            voiceState === 'listening'
              ? 'font-medium text-primary animate-pulse'
              : voiceState === 'processing'
              ? 'font-medium text-primary'
              : 'text-muted-foreground'
          }`}>
            {voiceState === 'idle' && 'Tap to speak'}
            {voiceState === 'listening' && 'Listening...'}
            {voiceState === 'processing' && 'Processing...'}
            {voiceState === 'done' && 'Command recognized'}
          </p>
        </div>

        {/* Transcript Area */}
        <div className="px-6 py-4 shrink-0">
          <p className={`text-xl font-medium min-h-[4rem] ${
            transcript ? 'text-foreground' : 'text-muted-foreground italic'
          }`}>
            {transcript || 'Try saying a command...'}
          </p>
        </div>

        {/* Response Area */}
        {result && (
          <div className="px-6 pb-4 shrink-0">
            <div className="bg-muted rounded-2xl p-4">
              <div className="flex items-start space-x-3">
                <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center shrink-0 mt-0.5">
                  <span className="material-icons-round text-primary text-sm">smart_toy</span>
                </div>
                <p className="text-sm text-foreground">{result.message}</p>
              </div>
              {result.navigateTo && (
                <button
                  onClick={() => { navigate(result.navigateTo!); onClose(); }}
                  className="mt-3 ml-11 text-xs font-semibold text-primary hover:underline"
                >
                  Go to page →
                </button>
              )}
            </div>
          </div>
        )}

        {/* Quick Command Chips */}
        <div className="px-6 py-4 flex-1 overflow-y-auto hide-scrollbar">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">Quick Commands</p>
          <div className="flex flex-wrap gap-2">
            {quickCommands.map((cmd) => (
              <button
                key={cmd}
                onClick={() => handleChipTap(cmd)}
                className="px-4 py-2.5 rounded-full bg-muted text-sm font-medium text-foreground hover:bg-accent cursor-pointer transition-colors"
              >
                {cmd}
              </button>
            ))}
          </div>
        </div>

        {/* Action Bar */}
        <div className="px-6 py-4 border-t border-border flex space-x-3 shrink-0">
          <button onClick={onClose} className="flex-1 py-3 rounded-xl border border-border text-muted-foreground font-semibold transition-all hover:bg-muted active:scale-[0.98]">
            Cancel
          </button>
          <button
            onClick={handleExecute}
            disabled={!result}
            className="flex-1 py-3 rounded-xl bg-primary text-primary-foreground font-semibold shadow-lg transition-all hover:bg-primary/90 active:scale-[0.98] disabled:opacity-50 disabled:pointer-events-none"
          >
            Execute
          </button>
        </div>
      </div>
    </>
  );
}

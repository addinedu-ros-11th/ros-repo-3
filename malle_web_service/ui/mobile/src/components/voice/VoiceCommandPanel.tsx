import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { parseVoiceCommand, type VoiceIntentResult, type VoiceActionContext } from '@/lib/voiceParser';
import { useAppStore } from '@/store/appStore';
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
} from '@/components/ui/drawer';

interface VoiceCommandPanelProps {
  open: boolean;
  onClose: () => void;
}

type VoiceState = 'idle' | 'listening' | 'processing' | 'done';

const quickCommands = [
  { label: 'Guide me to Zara', icon: 'near_me' },
  { label: 'Open lockbox slot 3', icon: 'lock_open' },
  { label: 'Follow mode tag 12', icon: 'person_pin_circle' },
  { label: 'Pickup from Nike', icon: 'shopping_bag' },
  { label: 'Show robot status', icon: 'smart_toy' },
  { label: 'Return to station', icon: 'home' },
  { label: 'Emergency stop', icon: 'emergency' },
  { label: 'Open map', icon: 'map' },
  { label: 'Shopping list', icon: 'receipt_long' },
];

export function VoiceCommandPanel({ open, onClose }: VoiceCommandPanelProps) {
  const [voiceState, setVoiceState] = useState<VoiceState>('idle');
  const [transcript, setTranscript] = useState('');
  const [result, setResult] = useState<VoiceIntentResult | null>(null);
  const navigate = useNavigate();

  const {
    stores, pois, addToGuideQueue, startFollowMe, stopFollowMe, setRobotMode, openSlot,
  } = useAppStore();

  const reset = useCallback(() => {
    setVoiceState('idle');
    setTranscript('');
    setResult(null);
  }, []);

  useEffect(() => {
    if (!open) reset();
  }, [open, reset]);

  /** Central processing – designed so real STT can call this with a transcript string */
  const processCommand = useCallback((command: string) => {
    setTranscript(command);
    setVoiceState('processing');
    setTimeout(() => {
      const intent = parseVoiceCommand(command, stores, pois);
      setResult(intent);
      setVoiceState('done');
    }, 600);
  }, [stores, pois]);

  const handleMicTap = () => {
    if (voiceState === 'listening' || voiceState === 'processing') return;
    reset();
    setVoiceState('listening');
    // TODO: Replace with real STT (e.g. ElevenLabs useScribe)
    setTimeout(() => {
      processCommand('Guide me to Nike store');
    }, 2000);
  };

  const handleChipTap = (command: string) => {
    reset();
    processCommand(command);
  };

  const buildActionContext = useCallback((): VoiceActionContext => ({
    stores, pois, addToGuideQueue, startFollowMe, stopFollowMe, setRobotMode, openSlot,
    navigate,
  }), [stores, pois, addToGuideQueue, startFollowMe, stopFollowMe, setRobotMode, openSlot, navigate]);

  const handleExecute = () => {
    if (!result) return;
    // Run side-effect action first
    if (result.action) {
      result.action(buildActionContext());
    }
    // Then navigate
    if (result.navigateTo) {
      navigate(result.navigateTo);
    }
    onClose();
  };

  const intentIcon = (intent: string) => {
    const map: Record<string, string> = {
      GUIDE: 'near_me', FOLLOW: 'person_pin_circle', PICKUP: 'shopping_bag',
      LOCKBOX: 'lock', MAP: 'map', STATUS: 'smart_toy', STOP: 'emergency',
      RETURN: 'home', LIST: 'receipt_long', UNKNOWN: 'help_outline',
    };
    return map[intent] || 'smart_toy';
  };

  return (
    <Drawer open={open} onOpenChange={(o) => !o && onClose()}>
      <DrawerContent className="max-h-[85vh] max-w-[430px] mx-auto">
        <DrawerHeader className="pb-2">
          <DrawerTitle className="text-lg font-bold flex items-center gap-2">
            <span className="material-icons-round text-primary text-xl">mic</span>
            Voice Command
          </DrawerTitle>
        </DrawerHeader>

        <div className="px-4 pb-6 space-y-5 overflow-y-auto hide-scrollbar">
          {/* Mic Button Area */}
          <div className="flex flex-col items-center py-3">
            <button
              onClick={handleMicTap}
              className="relative w-20 h-20 rounded-full flex items-center justify-center transition-all active:scale-90"
              style={{
                background: voiceState === 'listening'
                  ? 'linear-gradient(135deg, hsl(var(--primary)), hsl(var(--accent)))'
                  : 'hsl(var(--muted))',
              }}
            >
              {voiceState === 'listening' && (
                <>
                  <span className="absolute inset-0 rounded-full animate-ping bg-primary/20" />
                  <span className="absolute inset-[-8px] rounded-full animate-pulse bg-primary/10" />
                </>
              )}
              {voiceState === 'processing' ? (
                <span className="material-icons-round text-primary text-3xl animate-spin">sync</span>
              ) : (
                <span className={`material-icons-round text-3xl ${
                  voiceState === 'listening' ? 'text-white' : 'text-primary'
                }`}>mic</span>
              )}
            </button>
            <p className="mt-3 text-sm font-medium text-muted-foreground">
              {voiceState === 'idle' && 'Tap to speak'}
              {voiceState === 'listening' && 'Listening...'}
              {voiceState === 'processing' && 'Processing...'}
              {voiceState === 'done' && 'Command recognized'}
            </p>
          </div>

          {/* Transcript */}
          {transcript && (
            <div className="bg-muted/50 rounded-xl p-4">
              <p className="text-sm text-foreground font-medium">{transcript}</p>
            </div>
          )}

          {/* Result */}
          {result && (
            <div className={`border rounded-xl p-4 ${
              result.intent === 'UNKNOWN' ? 'bg-destructive/5 border-destructive/20' : 'bg-primary/5 border-primary/10'
            }`}>
              <div className="flex items-start gap-3">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 ${
                  result.intent === 'UNKNOWN' ? 'bg-destructive/10' : 'bg-primary/10'
                }`}>
                  <span className={`material-icons-round text-sm ${
                    result.intent === 'UNKNOWN' ? 'text-destructive' : 'text-primary'
                  }`}>{intentIcon(result.intent)}</span>
                </div>
                <div className="flex-1">
                  <p className="text-sm text-foreground">{result.message}</p>
                </div>
              </div>
            </div>
          )}

          {/* Quick Commands */}
          <div>
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Quick Commands</p>
            <div className="flex flex-wrap gap-2">
              {quickCommands.map((cmd) => (
                <button
                  key={cmd.label}
                  onClick={() => handleChipTap(cmd.label)}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-full bg-muted text-xs font-medium text-foreground hover:bg-accent transition-colors active:scale-95"
                >
                  <span className="material-icons-round text-muted-foreground" style={{ fontSize: 14 }}>{cmd.icon}</span>
                  {cmd.label}
                </button>
              ))}
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-2">
            <button
              onClick={onClose}
              className="flex-1 py-3 rounded-xl bg-muted text-foreground font-semibold text-sm active:scale-95 transition-transform"
            >
              Cancel
            </button>
            <button
              onClick={handleExecute}
              disabled={voiceState !== 'done' || result?.intent === 'UNKNOWN'}
              className="flex-1 py-3 rounded-xl bg-primary text-primary-foreground font-semibold text-sm active:scale-95 transition-transform disabled:opacity-40"
            >
              Execute
            </button>
          </div>
        </div>
      </DrawerContent>
    </Drawer>
  );
}

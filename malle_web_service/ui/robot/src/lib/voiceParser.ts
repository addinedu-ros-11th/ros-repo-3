import type { VoiceIntent } from '@/types/robot';
import { stores } from '@/data/stores';

export function parseVoiceCommand(rawText: string): VoiceIntent {
  const text = rawText.toLowerCase().trim();

  // GUIDE_TO: "guide me to zara", "navigate to nike", "go to apple"
  const guideMatch = text.match(/(?:guide\s+(?:me\s+)?to|navigate\s+to|go\s+to|take\s+me\s+to)\s+(.+)/i);
  if (guideMatch) {
    const destination = guideMatch[1].trim();
    return { type: 'GUIDE_TO', destination };
  }

  // OPEN_LOCKBOX: "open lockbox 3", "lockbox slot 3", "open slot 3", "unlock slot 3"
  const lockboxMatch = text.match(/(?:open|unlock)\s+(?:lockbox\s+)?(?:slot\s+)?(\d+)|lockbox\s+slot\s+(\d+)/i);
  if (lockboxMatch) {
    const slotId = parseInt(lockboxMatch[1] || lockboxMatch[2], 10);
    return { type: 'OPEN_LOCKBOX', slotId };
  }

  // START_FOLLOW: "follow tag 12", "start follow mode with tag 12", "start following 12"
  const followMatch = text.match(/(?:follow|start\s+follow(?:ing)?)\s+(?:mode\s+)?(?:with\s+)?(?:tag\s+)?#?(\d+)/i);
  if (followMatch) {
    const tagId = parseInt(followMatch[1], 10);
    return { type: 'START_FOLLOW', tagId };
  }

  // CREATE_PICKUP: "create pickup order from nike", "pickup from zara", "order from starbucks"
  const pickupMatch = text.match(/(?:create\s+)?(?:pickup|order)\s+(?:order\s+)?(?:from|at)\s+(.+)/i);
  if (pickupMatch) {
    const storeName = pickupMatch[1].trim();
    return { type: 'CREATE_PICKUP', storeName };
  }

  // EMERGENCY_STOP
  if (/emergency\s+stop|e[\-\s]?stop/i.test(text)) {
    return { type: 'EMERGENCY_STOP' };
  }

  // RETURN_TO_STATION
  if (/return\s+to\s+station|go\s+(?:back\s+)?home|return\s+home/i.test(text)) {
    return { type: 'RETURN_TO_STATION' };
  }

  // SHOW_STATUS
  if (/(?:show|display|what(?:'s| is))\s+(?:robot\s+)?status|robot\s+status/i.test(text)) {
    return { type: 'SHOW_STATUS' };
  }

  return { type: 'UNKNOWN', rawText };
}

/**
 * Resolve a fuzzy store name to a known store id.
 */
export function resolveStoreName(input: string): typeof stores[0] | undefined {
  const lower = input.toLowerCase();
  return stores.find(
    (s) =>
      s.name.toLowerCase() === lower ||
      s.name.toLowerCase().includes(lower) ||
      lower.includes(s.name.toLowerCase())
  );
}

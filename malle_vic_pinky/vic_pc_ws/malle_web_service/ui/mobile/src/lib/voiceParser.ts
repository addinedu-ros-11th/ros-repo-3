import type { POI } from '@/store/appStore';

export interface VoiceIntentResult {
  intent: string;
  message: string;
  navigateTo?: string;
  /** Action to run on Execute – receives store helpers */
  action?: (ctx: VoiceActionContext) => void;
}

export interface VoiceActionContext {
  stores: { id: string; name: string }[];
  pois: POI[];
  addToGuideQueue: (poi: POI) => void;
  startFollowMe: (tag: 11 | 12 | 13) => void;
  stopFollowMe: () => void;
  setRobotMode: (mode: 'GUIDE' | 'FOLLOW' | 'PICKUP' | null) => void;
  openSlot: (n: number) => void;
  navigate: (path: string) => void;
}

function fuzzyMatchStore(name: string, stores: { id: string; name: string }[]): { id: string; name: string } | null {
  const lower = name.toLowerCase().replace(/\s*store\s*/g, '').trim();
  return stores.find(s => s.name.toLowerCase().includes(lower) || lower.includes(s.name.toLowerCase())) ?? null;
}

function fuzzyMatchPoi(name: string, pois: POI[]): POI | null {
  const lower = name.toLowerCase().replace(/\s*store\s*/g, '').trim();
  return pois.find(p => p.name.toLowerCase().includes(lower) || lower.includes(p.name.toLowerCase())) ?? null;
}

export function parseVoiceCommand(command: string, stores: { id: string; name: string }[], pois: POI[]): VoiceIntentResult {
  const lower = command.toLowerCase();

  // --- GUIDE ---
  if (lower.includes('guide') && lower.includes('to')) {
    const match = lower.match(/guide\s+(?:me\s+)?to\s+(.+)/i);
    const storeName = match?.[1]?.trim() || '';
    const poi = fuzzyMatchPoi(storeName, pois);

    if (poi) {
      return {
        intent: 'GUIDE',
        message: `Adding ${poi.name} to guide queue and navigating to Guide mode.`,
        navigateTo: '/mode/guide',
        action: (ctx) => {
          ctx.addToGuideQueue(poi);
          ctx.setRobotMode('GUIDE');
        },
      };
    }
    return {
      intent: 'GUIDE',
      message: `Could not find "${storeName}". Opening Guide mode so you can choose.`,
      navigateTo: '/mode/guide',
    };
  }

  // --- FOLLOW ME ---
  if (lower.includes('follow') && (lower.includes('mode') || lower.includes('me') || lower.includes('tag'))) {
    const tagMatch = lower.match(/tag\s+(\d+)/);
    const tagNum = tagMatch ? Number(tagMatch[1]) : 11;
    const validTag = ([11, 12, 13] as const).includes(tagNum as 11 | 12 | 13) ? (tagNum as 11 | 12 | 13) : 11;
    return {
      intent: 'FOLLOW',
      message: `Starting Follow Me with AprilTag #${validTag}.`,
      navigateTo: '/mode/follow',
      action: (ctx) => {
        ctx.startFollowMe(validTag);
      },
    };
  }

  // --- PICKUP ---
  if (lower.includes('pickup') || lower.includes('pick up') || lower.includes('order')) {
    const storeMatch = lower.match(/(?:from|order)\s+(.+)/i);
    const storeName = storeMatch?.[1]?.trim() || '';
    const matched = fuzzyMatchStore(storeName, stores);

    if (matched) {
      return {
        intent: 'PICKUP',
        message: `Opening pickup order for ${matched.name}.`,
        navigateTo: `/mode/pickup?store=${matched.id}`,
      };
    }
    return {
      intent: 'PICKUP',
      message: storeName ? `Could not find "${storeName}". Opening Pickup mode.` : 'Opening Pickup mode.',
      navigateTo: '/mode/pickup',
    };
  }

  // --- LOCKBOX ---
  if (lower.includes('lockbox') || lower.includes('slot')) {
    const slotMatch = lower.match(/slot\s+(\d+)/);
    const slot = slotMatch ? Number(slotMatch[1]) : null;

    if (slot && slot >= 1 && slot <= 5) {
      return {
        intent: 'LOCKBOX',
        message: `Opening lockbox slot ${slot}.`,
        navigateTo: '/lockbox',
        action: (ctx) => {
          ctx.openSlot(slot);
        },
      };
    }
    return {
      intent: 'LOCKBOX',
      message: 'Opening lockbox management.',
      navigateTo: '/lockbox',
    };
  }

  // --- MAP ---
  if (lower.includes('map') || lower.includes('show map')) {
    return {
      intent: 'MAP',
      message: 'Opening mall map.',
      navigateTo: '/map',
    };
  }

  // --- STATUS ---
  if (lower.includes('status') || lower.includes('robot status')) {
    return {
      intent: 'STATUS',
      message: 'Showing current robot status on Home.',
      navigateTo: '/',
    };
  }

  // --- EMERGENCY STOP ---
  if (lower.includes('emergency') || (lower.includes('stop') && !lower.includes('follow'))) {
    return {
      intent: 'STOP',
      message: 'Emergency stop issued. All robot operations halted.',
      action: (ctx) => {
        ctx.stopFollowMe();
        ctx.setRobotMode(null);
      },
    };
  }

  // --- RETURN TO STATION ---
  if (lower.includes('return') || lower.includes('station')) {
    return {
      intent: 'RETURN',
      message: 'Robot returning to station.',
      navigateTo: '/',
      action: (ctx) => {
        ctx.setRobotMode(null);
      },
    };
  }

  // --- SHOPPING LIST ---
  if (lower.includes('list') || lower.includes('shopping')) {
    return {
      intent: 'LIST',
      message: 'Opening shopping list.',
      navigateTo: '/list',
    };
  }

  return {
    intent: 'UNKNOWN',
    message: `Sorry, I didn't understand "${command}". Try "Guide me to Zara" or "Pickup from Nike".`,
  };
}

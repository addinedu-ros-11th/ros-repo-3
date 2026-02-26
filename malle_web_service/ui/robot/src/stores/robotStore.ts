import { create } from 'zustand';
import type {
  SessionState,
  Robot,
  Session,
  ActiveMode,
  GuideState,
  GuideQueueItem,
  FollowState,
  FollowTag,
  FollowStatus,
  PickupState,
  PickupOrder,
  LockboxSlot,
  LockboxLog,
  Notification,
  NotificationCategory,
  VoiceIntent,
  VoiceIntentResult,
} from '@/types/robot';
import { parseVoiceCommand, resolveStoreName } from '@/lib/voiceParser';
import { stores, getProductsByStore } from '@/data/stores';
import { sessionApi } from '@/api/sessions';
import { guideApi } from '@/api/guide';
import { pickupApi, lockboxApi } from '@/api/services';

interface RobotStore {
  // ★ Server IDs
  currentSessionId: number | null;
  currentRobotId: number | null;

  // Robot State
  sessionState: SessionState;
  robot: Robot;
  session: Session | null;
  activeMode: ActiveMode;
  sessionTime: number;

  // Guide State
  guide: GuideState;

  // Follow State
  follow: FollowState;

  // Pickup State
  pickup: PickupState;

  // Lockbox State
  lockboxSlots: LockboxSlot[];
  lockboxLogs: LockboxLog[];

  // Notifications
  notifications: Notification[];
  notificationPanelOpen: boolean;

  // PIN Overlay
  showPinOverlay: boolean;

  // Actions - Session
  setSessionState: (state: SessionState) => void;
  startSession: (type: 'TASK' | 'TIME', remainingTime: number, customerName: string) => void;
  endSession: () => void;
  incrementSessionTime: () => void;
  decrementRemainingTime: () => void;

  // Actions - Robot
  setRobotStatus: (status: Robot['status']) => void;
  setBattery: (battery: number) => void;

  // Actions - Mode
  setActiveMode: (mode: ActiveMode) => void;

  // Actions - Guide
  addToGuideQueue: (item: Omit<GuideQueueItem, 'id' | 'serverItemId' | 'status' | 'selected'>) => void;
  removeFromGuideQueue: (id: string) => void;
  clearGuideQueue: () => void;
  toggleGuideItemSelection: (id: string) => void;
  selectAllGuideItems: (selected: boolean) => void;
  startGuide: () => void;
  stopGuide: () => void;
  advanceGuide: () => void;
  setGuideItemStatus: (id: string, status: GuideQueueItem['status']) => void;

  // Actions - Follow
  startFollow: (tagNumber: FollowTag) => void;
  stopFollow: () => void;
  setFollowStatus: (status: FollowStatus) => void;
  changeFollowTag: (tagNumber: FollowTag) => void;

  // Actions - Pickup
  createPickupOrder: (order: Omit<PickupOrder, 'status'>) => void;
  setPickupStatus: (status: PickupOrder['status']) => void;
  completePickup: () => void;
  setShowLoadingOverlay: (show: boolean) => void;

  // Actions - Lockbox
  setSlotStatus: (slotNumber: number, status: LockboxSlot['status'], orderInfo?: LockboxSlot['orderInfo']) => void;
  addLockboxLog: (log: Omit<LockboxLog, 'id'>) => void;
  openSlot: (slotNumber: number) => void;

  // Actions - Notifications
  addNotification: (notification: Omit<Notification, 'id' | 'timestamp' | 'read'>) => void;
  markNotificationRead: (id: string) => void;
  markAllNotificationsRead: () => void;
  toggleNotificationPanel: () => void;

  // Actions - PIN
  setShowPinOverlay: (show: boolean) => void;
  verifyPin: (pin: string) => boolean;

  // Actions - Voice Intent
  pendingLockboxSlot: number | null;
  pendingPickupStore: string | null;
  setPendingLockboxSlot: (slot: number | null) => void;
  setPendingPickupStore: (store: string | null) => void;
  executeVoiceIntent: (intent: VoiceIntent) => VoiceIntentResult;

  // ★ WS-driven (useWsHandler 전용)
  _setGuideQueueFromServer: (queue: GuideQueueItem[]) => void;
}

const initialRobot: Robot = {
  id: '1',
  name: 'Mall·E-1',
  battery: 78,
  networkStrength: 'Strong',
  status: 'IDLE',
};

const initialLockboxSlots: LockboxSlot[] = [
  { number: 1, status: 'FULL', occupiedSince: '10:30 AM', isPickupOrder: true, pickedUp: true, orderInfo: { orderId: '#7743', storeName: 'Zara', customerName: 'Sarah' } },
  { number: 2, status: 'FULL', occupiedSince: '11:15 AM' },
  { number: 3, status: 'RESERVED', orderInfo: { orderId: '#8821', storeName: 'Zara Store', customerName: 'Sarah' } },
  { number: 4, status: 'EMPTY' },
  { number: 5, status: 'EMPTY' },
];

const initialLockboxLogs: LockboxLog[] = [
  { id: '1', timestamp: '10:30 AM', slotNumber: 1, action: 'SECURED', result: 'SUCCESS', description: 'Slot 1 locked after item storage' },
  { id: '2', timestamp: '10:15 AM', slotNumber: 2, action: 'OPENED', result: 'SUCCESS', description: 'Slot 2 opened for retrieval' },
  { id: '3', timestamp: '09:45 AM', slotNumber: 3, action: 'SECURED', result: 'SUCCESS', description: 'Slot 3 reserved for pickup order' },
];

const initialNotifications: Notification[] = [
  { id: '1', category: 'NAVIGATION', title: 'Arrived at Zara', description: 'Waiting for customer', timestamp: new Date(Date.now() - 30 * 60000), read: false },
  { id: '2', category: 'LOCKBOX', title: 'Slot 2 Opened', description: 'Successful retrieval', timestamp: new Date(Date.now() - 45 * 60000), read: true },
  { id: '3', category: 'PICKUP', title: 'New Pickup Order', description: 'Order #8821 from Zara', timestamp: new Date(Date.now() - 60 * 60000), read: true },
  { id: '4', category: 'SYSTEM', title: 'Battery Low Warning', description: 'Battery at 25%', timestamp: new Date(Date.now() - 75 * 60000), read: true },
];

/* localId 충돌 방지용 카운터 (Date.now()는 동기 루프에서 중복됨) */
let _guideLocalSeq = 0;

export const useRobotStore = create<RobotStore>((set, get) => ({
  // ★ Server IDs
  currentSessionId: null,
  currentRobotId: null,

  // Initial State
  sessionState: 'INACTIVE',
  robot: initialRobot,
  session: null,
  activeMode: null,
  sessionTime: 0,

  guide: { queue: [], isExecuting: false, currentDestinationIndex: 0 },
  follow: { active: false, tagNumber: null, status: 'STOPPED' },
  pickup: { currentOrder: null, showLoadingOverlay: false },

  lockboxSlots: initialLockboxSlots,
  lockboxLogs: initialLockboxLogs,
  notifications: initialNotifications,
  notificationPanelOpen: false,
  showPinOverlay: false,
  pendingLockboxSlot: null,
  pendingPickupStore: null,

  // ── Session ──────────────────────────────────────────────────────────────

  setSessionState: (state) => set({ sessionState: state }),

  startSession: (type, remainingTime, customerName) => set({
    sessionState: 'ACTIVE',
    session: { type, remainingTime, customerId: 'customer-1', customerName },
    sessionTime: 0,
    showPinOverlay: false,
  }),

  endSession: () => {
    const { currentSessionId } = get();
    if (currentSessionId) sessionApi.end(currentSessionId).catch(() => {});
    set({
      sessionState: 'INACTIVE',
      session: null,
      activeMode: null,
      sessionTime: 0,
      guide: { queue: [], isExecuting: false, currentDestinationIndex: 0 },
      follow: { active: false, tagNumber: null, status: 'STOPPED' },
      pickup: { currentOrder: null, showLoadingOverlay: false },
      currentSessionId: null,
    });
  },

  incrementSessionTime: () => set((state) => ({ sessionTime: state.sessionTime + 1 })),

  decrementRemainingTime: () => set((state) => ({
    session: state.session
      ? { ...state.session, remainingTime: Math.max(0, state.session.remainingTime - 1) }
      : null,
  })),

  // ── Robot ────────────────────────────────────────────────────────────────

  setRobotStatus: (status) => set((state) => ({ robot: { ...state.robot, status } })),
  setBattery: (battery) => set((state) => ({ robot: { ...state.robot, battery } })),

  // ── Mode ─────────────────────────────────────────────────────────────────

  setActiveMode: (mode) => set({ activeMode: mode }),

  // ── Guide ────────────────────────────────────────────────────────────────

  addToGuideQueue: (item) => {
    const localId = `guide-local-${++_guideLocalSeq}`;
    set((state) => ({
      guide: {
        ...state.guide,
        queue: [...state.guide.queue, {
          ...item,
          id: localId,
          serverItemId: null,  // API 응답 후 채움
          status: 'PENDING',
          selected: true,
        }],
      },
    }));
    // poi_id는 poiId 필드에서 숫자로 변환
    const { currentSessionId } = get();
    if (currentSessionId && item.poiId) {
      guideApi.addToQueue(currentSessionId, Number(item.poiId))
        .then((res) => {
          set((state) => ({
            guide: {
              ...state.guide,
              queue: state.guide.queue.map((q) =>
                q.id === localId ? { ...q, serverItemId: res.id } : q
              ),
            },
          }));
        })
        .catch(() => {});
    }
  },

  removeFromGuideQueue: (id) => {
    // 삭제 전 serverItemId 조회
    const item = get().guide.queue.find((q) => q.id === id);
    set((state) => ({
      guide: { ...state.guide, queue: state.guide.queue.filter((q) => q.id !== id) },
    }));
    const { currentSessionId } = get();
    if (currentSessionId && item?.serverItemId) {
      guideApi.removeFromQueue(currentSessionId, item.serverItemId).catch(() => {});
    }
  },

  clearGuideQueue: () => {
    set((state) => ({ guide: { ...state.guide, queue: [] } }));
    const { currentSessionId } = get();
    if (currentSessionId) guideApi.clear(currentSessionId).catch(() => {});
  },

  toggleGuideItemSelection: (id) => set((state) => ({
    guide: {
      ...state.guide,
      queue: state.guide.queue.map((item) =>
        item.id === id ? { ...item, selected: !item.selected } : item
      ),
    },
  })),

  selectAllGuideItems: (selected) => set((state) => ({
    guide: { ...state.guide, queue: state.guide.queue.map((item) => ({ ...item, selected })) },
  })),

  startGuide: () => {
    const state = get();
    const selectedItems = state.guide.queue.filter((item) => item.selected);
    if (selectedItems.length === 0) return;
    set({ activeMode: 'GUIDE', guide: { ...state.guide, isExecuting: true, currentDestinationIndex: 0 } });
    if (state.currentSessionId) guideApi.execute(state.currentSessionId).catch(() => {});
  },

  stopGuide: () => set((state) => ({
    activeMode: null,
    guide: { ...state.guide, isExecuting: false, currentDestinationIndex: 0 },
  })),

  advanceGuide: () => set((state) => {
    const selectedItems = state.guide.queue.filter((item) => item.selected);
    const nextIndex = state.guide.currentDestinationIndex + 1;
    if (nextIndex >= selectedItems.length) {
      return { activeMode: null, guide: { queue: [], isExecuting: false, currentDestinationIndex: 0 } };
    }
    return { guide: { ...state.guide, currentDestinationIndex: nextIndex } };
  }),

  setGuideItemStatus: (id, status) => set((state) => ({
    guide: {
      ...state.guide,
      queue: state.guide.queue.map((item) => item.id === id ? { ...item, status } : item),
    },
  })),

  // ★ WS-driven: 서버 큐와 로컬 낙관적 항목 병합
  _setGuideQueueFromServer: (serverQueue) => set((state) => {
    // 서버 큐에 이미 반영된 poiId 집합
    const serverPoiIds = new Set(serverQueue.map((i) => i.poiId));

    // serverItemId === null이고 서버 큐에 없는 poiId의 낙관적 항목만 유지
    const pendingOptimistic = state.guide.queue.filter(
      (i) => i.serverItemId === null && !serverPoiIds.has(i.poiId)
    );

    // 서버 큐 항목에 기존 선택 상태 병합
    const mergedServerItems = serverQueue.map((serverItem) => {
      const existing = state.guide.queue.find((i) => i.serverItemId === serverItem.serverItemId);
      return existing ? { ...serverItem, selected: existing.selected } : serverItem;
    });

    return { guide: { ...state.guide, queue: [...mergedServerItems, ...pendingOptimistic] } };
  }),

  // ── Follow ───────────────────────────────────────────────────────────────

  startFollow: (tagNumber) => {
    set((state) => ({
      activeMode: 'FOLLOW',
      follow: { active: true, tagNumber, status: 'FOLLOWING' },
      robot: { ...state.robot, status: 'MOVING' },
    }));
    const { currentSessionId } = get();
    if (currentSessionId && tagNumber) {
      sessionApi.setFollowTag(currentSessionId, tagNumber).catch(() => {});
    }
  },

  stopFollow: () => set((state) => ({
    activeMode: null,
    follow: { active: false, tagNumber: null, status: 'STOPPED' },
    robot: { ...state.robot, status: 'IDLE' },
  })),

  setFollowStatus: (status) => set((state) => ({ follow: { ...state.follow, status } })),
  changeFollowTag: (tagNumber) => set((state) => ({ follow: { ...state.follow, tagNumber } })),

  // ── Pickup ───────────────────────────────────────────────────────────────

  createPickupOrder: (order) => {
    const state = get();
    const emptySlotIndex = state.lockboxSlots.findIndex((slot) => slot.status === 'EMPTY');
    if (emptySlotIndex === -1) return;
    const slotNumber = state.lockboxSlots[emptySlotIndex].number;

    set((state) => ({
      activeMode: 'PICKUP',
      robot: { ...state.robot, status: 'MOVING' },
      pickup: { currentOrder: { ...order, status: 'MOVING', slotId: slotNumber }, showLoadingOverlay: false },
      lockboxSlots: state.lockboxSlots.map((slot, i) =>
        i === emptySlotIndex
          ? { ...slot, status: 'RESERVED' as const, orderInfo: { orderId: order.orderId, storeName: order.storeName, customerName: 'Customer' } }
          : slot
      ),
    }));

    if (state.currentSessionId) {
      pickupApi.create(state.currentSessionId, {
        pickup_poi_id: 1, // TODO: store → poi_id 매핑
        created_channel: 'ROBOT',
        items: order.items.map((it, i) => ({ product_id: i + 1, qty: it.quantity, unit_price: it.price })),
      }).catch(() => {});
    }
  },

  setPickupStatus: (status) => set((state) => ({
    pickup: state.pickup.currentOrder
      ? { ...state.pickup, currentOrder: { ...state.pickup.currentOrder, status } }
      : state.pickup,
  })),

  completePickup: () => {
    const state = get();
    if (!state.pickup.currentOrder) return;
    const slotNumber = state.pickup.currentOrder.slotId;
    set((state) => ({
      activeMode: null,
      robot: { ...state.robot, status: 'IDLE' },
      pickup: { currentOrder: null, showLoadingOverlay: false },
      lockboxSlots: state.lockboxSlots.map((slot) =>
        slot.number === slotNumber
          ? { ...slot, status: 'FULL' as const, isPickupOrder: true, pickedUp: true, occupiedSince: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }
          : slot
      ),
    }));
  },

  setShowLoadingOverlay: (show) => set((state) => ({
    pickup: { ...state.pickup, showLoadingOverlay: show },
  })),

  // ── Lockbox ──────────────────────────────────────────────────────────────

  setSlotStatus: (slotNumber, status, orderInfo) => set((state) => ({
    lockboxSlots: state.lockboxSlots.map((slot) =>
      slot.number === slotNumber
        ? {
            ...slot,
            status,
            orderInfo: orderInfo ?? (status === 'EMPTY' ? undefined : slot.orderInfo),
            occupiedSince: status === 'FULL'
              ? new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
              : undefined,
            isPickupOrder: status === 'RESERVED' ? true : status === 'EMPTY' ? false : (orderInfo ? true : false),
            pickedUp: false,
          }
        : slot
    ),
  })),

  addLockboxLog: (log) => set((state) => ({
    lockboxLogs: [{ ...log, id: crypto.randomUUID() }, ...state.lockboxLogs].slice(0, 20),
  })),

  openSlot: (slotNumber) => {
    const state = get();
    state.addLockboxLog({
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      slotNumber,
      action: 'OPENED',
      result: 'SUCCESS',
      description: `Slot ${slotNumber} opened`,
    });
    if (state.currentRobotId) lockboxApi.openSlot(state.currentRobotId, slotNumber).catch(() => {});
  },

  // ── Notifications ────────────────────────────────────────────────────────

  addNotification: (notification) => set((state) => ({
    notifications: [
      { ...notification, id: crypto.randomUUID(), timestamp: new Date(), read: false },
      ...state.notifications,
    ].slice(0, 50),
  })),

  markNotificationRead: (id) => set((state) => ({
    notifications: state.notifications.map((n) => n.id === id ? { ...n, read: true } : n),
  })),

  markAllNotificationsRead: () => set((state) => ({
    notifications: state.notifications.map((n) => ({ ...n, read: true })),
  })),

  toggleNotificationPanel: () => set((state) => ({
    notificationPanelOpen: !state.notificationPanelOpen,
  })),

  // ── PIN ──────────────────────────────────────────────────────────────────

  setShowPinOverlay: (show) => set({ showPinOverlay: show }),

  verifyPin: (pin) => {
    const { currentSessionId } = get();
    if (pin.length === 4) {
      if (currentSessionId) {
        sessionApi.verifyPin(currentSessionId, pin).catch(() => {});
      }
      set({ showPinOverlay: false });
      return true;
    }
    return false;
  },

  // ── Voice Intent ─────────────────────────────────────────────────────────

  setPendingLockboxSlot: (slot) => set({ pendingLockboxSlot: slot }),
  setPendingPickupStore: (store) => set({ pendingPickupStore: store }),

  executeVoiceIntent: (intent) => {
    const state = get();
    switch (intent.type) {
      case 'GUIDE_TO': {
        const store = resolveStoreName(intent.destination);
        if (!store) {
          return { success: false, message: `❌ Could not find "${intent.destination}". Try a different name.` };
        }
        if (!store.open) {
          return { success: false, message: `❌ ${store.name} is currently closed.` };
        }
        state.addToGuideQueue({
          poiId: store.id,
          poiName: store.name,
          floor: store.location,
          estimatedTime: Math.floor(Math.random() * 5) + 2,
        });
        return { success: true, message: `✅ Added ${store.name} to your Guide queue.`, navigateTo: '/mode/guide' };
      }
      case 'OPEN_LOCKBOX': {
        const slot = state.lockboxSlots.find((s) => s.number === intent.slotId);
        if (!slot) {
          return { success: false, message: `❌ Slot ${intent.slotId} does not exist.` };
        }
        if (slot.status === 'EMPTY') {
          return { success: false, message: `❌ Slot ${intent.slotId} is already empty.` };
        }
        set({ pendingLockboxSlot: intent.slotId });
        return { success: true, message: `✅ Opening lockbox slot ${intent.slotId}. Please verify with token.`, navigateTo: '/lockbox' };
      }
      case 'START_FOLLOW': {
        const validTags = [11, 12, 13];
        if (!validTags.includes(intent.tagId)) {
          return { success: false, message: `❌ Invalid tag. Use 11, 12, or 13.` };
        }
        state.startFollow(intent.tagId as 11 | 12 | 13);
        return { success: true, message: `✅ Follow mode activated with Tag #${intent.tagId}.`, navigateTo: '/mode/follow' };
      }
      case 'CREATE_PICKUP': {
        const store = resolveStoreName(intent.storeName);
        if (!store) {
          return { success: false, message: `❌ Could not find "${intent.storeName}".` };
        }
        if (!store.open) {
          return { success: false, message: `❌ ${store.name} is currently closed.` };
        }
        const hasEmpty = state.lockboxSlots.some((s) => s.status === 'EMPTY');
        if (!hasEmpty) {
          return { success: false, message: `❌ No empty lockbox slots available.` };
        }
        set({ pendingPickupStore: store.id });
        return { success: true, message: `✅ Starting pickup order from ${store.name}.`, navigateTo: '/mode/pickup' };
      }
      case 'EMERGENCY_STOP': {
        state.setRobotStatus('STOPPED');
        return { success: true, message: `🛑 Emergency stop activated. Robot has been stopped.` };
      }
      case 'RETURN_TO_STATION': {
        return { success: true, message: `🏠 Returning robot to the nearest station. Please confirm.` };
      }
      case 'SHOW_STATUS': {
        const r = state.robot;
        const mode = state.activeMode || 'None';
        return {
          success: true,
          message: `🤖 ${r.name} — Battery: ${r.battery}%, Network: ${r.networkStrength}, Status: ${r.status}, Mode: ${mode}`,
        };
      }
      case 'UNKNOWN':
        return { success: false, message: `I understood: "${intent.rawText}". I couldn't match this to a known command.` };
    }
  },
}));
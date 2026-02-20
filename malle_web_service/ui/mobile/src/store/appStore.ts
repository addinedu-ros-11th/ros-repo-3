import { create } from 'zustand';
import { sessionApi } from '@/api/sessions';
import { guideApi } from '@/api/guide';
import { pickupApi, lockboxApi, storeApi, poiApi, type PoiRes, type StoreRes } from '@/api/services';
import { storeProducts as hardcodedStoreProducts } from '@/data/storeProducts';

export type SessionState = 'NO_SESSION' | 'FINDING_ROBOT' | 'ROBOT_ASSIGNED' | 'APPROACHING' | 'PIN_MATCHING' | 'ACTIVE' | 'ENDED';
export type RobotMode = 'GUIDE' | 'FOLLOW' | 'PICKUP' | null;
export type SessionType = 'TASK' | 'TIME';
export type GuideStatus = 'PENDING' | 'IN_PROGRESS' | 'ARRIVED' | 'DONE';
export type FollowStatus = 'FOLLOWING' | 'LOST' | 'STOPPED' | 'RECONNECTING';
export type PickupStatus = 'IDLE' | 'MOVING' | 'LOADING' | 'LOADED' | 'MEETUP_SET' | 'RETURNING' | 'DONE';
export type LockboxStatus = 'FULL' | 'EMPTY' | 'RESERVED' | 'PICKED_UP';
export type TaskMissionType = 'GUIDE' | 'PICKUP';

export interface Robot {
  id: string;
  name: string;
  battery: number;
  mode: RobotMode;
  location: { x: number; y: number };
}

export interface Session {
  type: SessionType;
  duration: number;
  remainingTime: number;
  startedAt: Date | null;
}

export interface TaskMission {
  type: TaskMissionType;
  destinationPoi?: POI;
  storeId?: string;
  storeName?: string;
  items?: { name: string; quantity: number; price: number }[];
}

export interface GuideDestination {
  id: string;
  poiId: string;
  poiName: string;
  floor: string;
  estimatedTime: number;
  status: GuideStatus;
  selected: boolean;
}

export interface FollowMeState {
  active: boolean;
  tagNumber: 11 | 12 | 13;
  status: FollowStatus;
}

export interface PickupOrder {
  orderId: string;
  storeId: string;
  storeName: string;
  items: { name: string; quantity: number; price: number }[];
  status: PickupStatus;
  meetupLocation: string | null;
  slotId: number | null;
}

export interface LockboxSlot {
  slotNumber: number;
  status: LockboxStatus;
  occupiedSince?: string;
  orderInfo?: {
    orderId: string;
    storeName: string;
    customerName: string;
  };
}

export interface LockboxLog {
  id: string;
  timestamp: Date;
  slotNumber: number;
  action: 'OPENED' | 'SECURED' | 'FAILED';
  result: 'SUCCESS' | 'FAILURE';
  description: string;
}

export interface Store {
  id: string;
  name: string;
  category: string;
  location: string;
  icon: string;
  open: boolean;
  closeTime: string;
  openTime?: string;
}

export interface Product {
  id: string;
  storeId: string;
  name: string;
  option: string;
  price: number;
  completed: boolean;
}

export interface SearchState {
  query: string;
  filter: string;
  results: Store[];
  isOpen: boolean;
}

export interface POI {
  id: string;
  name: string;
  x: number;
  y: number;
  waitPoint: { x: number; y: number };
  category: string;
}

interface AppState {
  userName: string;
  userPhone: string;

  /** ★ 서버 연동용 ID */
  currentSessionId: number | null;
  currentRobotId: number | null;
  matchPin: string | null;

  sessionState: SessionState;
  robot: Robot | null;
  session: Session;
  taskMission: TaskMission | null;
  approachingEta: number;

  guideQueue: GuideDestination[];
  followMe: FollowMeState;
  pickupOrder: PickupOrder | null;

  lockboxSlots: LockboxSlot[];
  lockboxLogs: LockboxLog[];
  shoppingList: Product[];
  searchState: SearchState;
  stores: Store[];
  pois: POI[];
  storeProducts: Record<string, { name: string; option: string; price: number }[]>;

  /** ★ App mount 시 서버에서 stores/pois fetch */
  initFromServer: () => Promise<void>;

  setUserName: (name: string) => void;
  startFindingRobot: (type: SessionType, duration: number) => void;
  assignRobot: (robot: Robot) => void;
  startPinMatching: () => void;
  activateSession: () => void;
  endSession: () => void;
  setRobotMode: (mode: RobotMode) => void;
  updateRemainingTime: (seconds: number) => void;
  setTaskMission: (mission: TaskMission) => void;
  completeTaskSession: () => void;

  addToGuideQueue: (poi: POI) => void;
  removeFromGuideQueue: (id: string) => void;
  toggleGuideSelection: (id: string) => void;
  clearGuideQueue: () => void;
  startGuide: () => void;
  completeCurrentGuide: () => void;

  startFollowMe: (tagNumber: 11 | 12 | 13) => void;
  stopFollowMe: () => void;
  setFollowStatus: (status: FollowStatus) => void;

  createPickupOrder: (storeId: string, items: { name: string; quantity: number; price: number }[]) => void;
  setPickupStatus: (status: PickupStatus) => void;
  setMeetupLocation: (location: string) => void;

  openSlot: (slotNumber: number) => void;
  confirmSlotFull: (slotNumber: number) => void;
  confirmSlotEmpty: (slotNumber: number) => void;

  tickTimer: () => void;
  tickApproachingEta: () => void;

  toggleProductComplete: (id: string) => void;
  addToShoppingList: (product: Omit<Product, 'id' | 'completed'>) => void;
  removeFromShoppingList: (id: string) => void;

  setSearchOpen: (open: boolean) => void;
  setSearchQuery: (query: string) => void;
  setSearchFilter: (filter: string) => void;

  /** ★ WS 핸들러 전용 */
  _setGuideQueueFromServer: (queue: GuideDestination[]) => void;
  _updateRobotState: (data: { battery_pct?: number; x_m?: number; y_m?: number }) => void;
}

/* ───── fallback data ───── */

const initialStores: Store[] = [
  { id: 'zara', name: 'Zara', category: 'Fashion & Apparel', location: 'Level 2, Zone B', icon: 'checkroom', open: true, closeTime: '10:00 PM' },
  { id: 'nike', name: 'Nike', category: 'Sports & Outdoor', location: 'Level 1, Zone A', icon: 'sports_basketball', open: true, closeTime: '9:00 PM' },
  { id: 'apple', name: 'Apple', category: 'Electronics', location: 'Level 2, Zone C', icon: 'laptop_mac', open: true, closeTime: '9:30 PM' },
  { id: 'intersport', name: 'Intersport', category: 'Sports & Outdoor', location: 'Level 2, Zone B', icon: 'sports_basketball', open: true, closeTime: '9:00 PM' },
  { id: 'sportystyle', name: 'SportyStyle', category: 'Fashion & Apparel', location: 'Level 1, Zone A', icon: 'checkroom', open: true, closeTime: '10:00 PM' },
  { id: 'progym', name: 'ProGym Equipment', category: 'Fitness', location: 'Ground Floor', icon: 'fitness_center', open: false, closeTime: '9:00 PM', openTime: '9:00 AM' },
  { id: 'starbucks', name: 'Starbucks', category: 'Dining', location: 'Level 1, Zone B', icon: 'local_cafe', open: true, closeTime: '11:00 PM' },
  { id: 'hm', name: 'H&M', category: 'Fashion & Apparel', location: 'Level 1, Zone C', icon: 'checkroom', open: true, closeTime: '9:00 PM' },
];

const initialPOIs: POI[] = [
  { id: 'zara', name: 'Zara', x: 40, y: 90, waitPoint: { x: 38, y: 88 }, category: 'Fashion' },
  { id: 'nike', name: 'Nike', x: 280, y: 80, waitPoint: { x: 278, y: 78 }, category: 'Sports' },
  { id: 'apple', name: 'Apple', x: 160, y: 30, waitPoint: { x: 158, y: 28 }, category: 'Electronics' },
  { id: 'starbucks', name: 'Starbucks', x: 120, y: 150, waitPoint: { x: 118, y: 148 }, category: 'Dining' },
  { id: 'hm', name: 'H&M', x: 220, y: 120, waitPoint: { x: 218, y: 118 }, category: 'Fashion' },
  { id: 'intersport', name: 'Intersport', x: 300, y: 140, waitPoint: { x: 298, y: 138 }, category: 'Sports' },
  { id: 'sportystyle', name: 'SportyStyle', x: 60, y: 150, waitPoint: { x: 58, y: 148 }, category: 'Fashion' },
  { id: 'progym', name: 'ProGym Equipment', x: 200, y: 40, waitPoint: { x: 198, y: 38 }, category: 'Fitness' },
];

const initialLockboxSlots: LockboxSlot[] = [
  { slotNumber: 1, status: 'FULL', occupiedSince: '10:30 AM' },
  { slotNumber: 2, status: 'FULL', occupiedSince: '11:15 AM' },
  { slotNumber: 3, status: 'RESERVED', orderInfo: { orderId: '#8821', storeName: 'Zara Store', customerName: 'Sarah' } },
  { slotNumber: 4, status: 'EMPTY' },
  { slotNumber: 5, status: 'EMPTY' },
];

const initialLockboxLogs: LockboxLog[] = [
  { id: '1', timestamp: new Date(Date.now() - 3600000), slotNumber: 1, action: 'SECURED', result: 'SUCCESS', description: 'Items securely stored' },
  { id: '2', timestamp: new Date(Date.now() - 7200000), slotNumber: 2, action: 'OPENED', result: 'SUCCESS', description: 'Slot opened for storage' },
  { id: '3', timestamp: new Date(Date.now() - 10800000), slotNumber: 3, action: 'SECURED', result: 'FAILURE', description: 'Lock mechanism failed' },
];

const initialShoppingList: Product[] = [
  { id: '1', storeId: 'zara', name: 'Linen Blend Shirt', option: 'Size M, Beige', price: 45.90, completed: false },
  { id: '2', storeId: 'zara', name: 'Pleated Trousers', option: 'Size 32, Black', price: 59.90, completed: true },
  { id: '3', storeId: 'nike', name: 'Air Zoom Pegasus', option: 'Size 10, Grey/Volt', price: 120.00, completed: false },
  { id: '4', storeId: 'nike', name: 'Running Socks (3pk)', option: 'White', price: 18.00, completed: false },
  { id: '5', storeId: 'nike', name: 'Dri-FIT Headband', option: 'Black', price: 12.00, completed: true },
  { id: '6', storeId: 'apple', name: 'USB-C Charge Cable', option: '2m', price: 19.00, completed: false },
  { id: '7', storeId: 'starbucks', name: 'Tumbler', option: 'Grande, Green', price: 24.00, completed: false },
  { id: '8', storeId: 'hm', name: 'Basic T-Shirt', option: 'Size L, White', price: 9.99, completed: false },
];

/* ───── server → frontend mapping ───── */

const catIcon: Record<string, string> = {
  fashion: 'checkroom', sports: 'sports_basketball', electronics: 'laptop_mac',
  cafe: 'local_cafe', fitness: 'fitness_center', dining: 'local_cafe',
};
function mapStore(s: StoreRes): Store {
  const c = (s.category || 'other').toLowerCase();
  return { id: String(s.id), name: s.name || `Store #${s.id}`, category: s.category || 'Other',
    location: `(${s.x_m?.toFixed(0) ?? 0}, ${s.y_m?.toFixed(0) ?? 0})`,
    icon: catIcon[c] || 'store', open: true, closeTime: '9:00 PM' };
}
function mapPoi(p: PoiRes): POI {
  return { id: String(p.id), name: p.name, x: p.x_m, y: p.y_m,
    waitPoint: { x: p.wait_x_m ?? p.x_m - 2, y: p.wait_y_m ?? p.y_m - 2 },
    category: p.type || 'OTHER' };
}

/* ==================== STORE ==================== */

export const useAppStore = create<AppState>((set, get) => ({
  userName: 'Sarah',
  userPhone: '+1 (555) 123-4567',
  currentSessionId: null,
  currentRobotId: null,
  matchPin: null,

  sessionState: 'NO_SESSION',
  robot: null,
  session: { type: 'TIME', duration: 120, remainingTime: 7200, startedAt: null },
  taskMission: null,
  approachingEta: 10,
  guideQueue: [],
  followMe: { active: false, tagNumber: 11, status: 'STOPPED' },
  pickupOrder: null,
  lockboxSlots: initialLockboxSlots,
  lockboxLogs: initialLockboxLogs,
  shoppingList: initialShoppingList,
  searchState: { query: '', filter: 'All', results: initialStores, isOpen: false },
  stores: initialStores,
  pois: initialPOIs,
  storeProducts: hardcodedStoreProducts,

  /* ★ 서버에서 stores/pois 로드 (App mount 시 1회) */
  initFromServer: async () => {
    try {
      const [sr, pr] = await Promise.all([
        storeApi.list().catch(() => null),
        poiApi.list().catch(() => null),
      ]);
      const u: Partial<AppState> = {};
      if (sr?.length) { const m = sr.map(mapStore); u.stores = m; u.searchState = { ...get().searchState, results: m }; }
      if (pr?.length) u.pois = pr.map(mapPoi);

      // ★ store별 products fetch (DB 연결 시)
      if (sr?.length) {
        const productsMap: Record<string, { name: string; option: string; price: number }[]> = {};
        const results = await Promise.all(
          sr.map(s => storeApi.getProducts(s.id).catch(() => null))
        );
        sr.forEach((s, i) => {
          const products = results[i];
          if (products?.length) {
            productsMap[String(s.id)] = products.map(p => ({
              name: p.name,
              option: p.sku || '',
              price: p.price,
            }));
          }
        });
        if (Object.keys(productsMap).length) u.storeProducts = productsMap;
      }

      if (Object.keys(u).length) set(u);
    } catch { /* fallback data 유지 */ }
  },

  /* ───── Session ───── */

  setUserName: (name) => set({ userName: name }),

  startFindingRobot: (type, duration) => {
    // optimistic UI
    set({ sessionState: 'FINDING_ROBOT', session: { type, duration, remainingTime: duration * 60, startedAt: null }, approachingEta: 10 });
    // ★ API → 서버가 로봇 배정 후 WS SESSION_ASSIGNED 전송
    sessionApi.create({ user_id: 1, session_type: type, requested_minutes: type === 'TIME' ? duration : undefined })
      .then((res) => {
        set({ currentSessionId: res.id, matchPin: res.match_pin });
        if (res.assigned_robot_id && res.status === 'ASSIGNED') {
          set({ currentRobotId: res.assigned_robot_id, sessionState: 'APPROACHING',
            robot: { id: String(res.assigned_robot_id), name: `Mall·E-${res.assigned_robot_id}`, battery: 80, mode: null, location: { x: 0, y: 0 } } });
        }
      }).catch((e) => console.error('[API] session create:', e));
  },

  assignRobot: (robot) => set({ sessionState: 'APPROACHING', robot: { ...robot, name: robot.name.replace('PinkyPro', 'Mall·E') } }),
  startPinMatching: () => set({ sessionState: 'PIN_MATCHING', approachingEta: 0 }),

  activateSession: () => set((state) => {
    const updates: Partial<AppState> = { sessionState: 'ACTIVE', session: { ...state.session, startedAt: new Date() } };
    if (state.session.type === 'TASK' && state.taskMission) {
      if (state.taskMission.type === 'GUIDE' && state.taskMission.destinationPoi) {
        const poi = state.taskMission.destinationPoi;
        updates.guideQueue = [{ id: `guide-task-${Date.now()}`, poiId: poi.id, poiName: poi.name, floor: 'Level 1', estimatedTime: Math.floor(Math.random() * 5) + 2, status: 'PENDING', selected: true }];
        updates.robot = state.robot ? { ...state.robot, mode: 'GUIDE' } : null;
        if (state.currentSessionId) guideApi.addToQueue(state.currentSessionId, Number(poi.id)).catch(() => {});
      } else if (state.taskMission.type === 'PICKUP' && state.taskMission.storeId && state.taskMission.items) {
        const store = state.stores.find(s => s.id === state.taskMission!.storeId);
        const emptySlot = state.lockboxSlots.find(s => s.status === 'EMPTY');
        const orderId = `#${Math.floor(1000 + Math.random() * 9000)}`;
        updates.pickupOrder = { orderId, storeId: state.taskMission.storeId, storeName: store?.name || state.taskMission.storeName || 'Unknown Store', items: state.taskMission.items, status: 'MOVING', meetupLocation: null, slotId: emptySlot?.slotNumber || null };
        if (emptySlot) updates.lockboxSlots = state.lockboxSlots.map(slot => slot.slotNumber === emptySlot.slotNumber ? { ...slot, status: 'RESERVED' as LockboxStatus, orderInfo: { orderId, storeName: store?.name || 'Unknown Store', customerName: state.userName } } : slot);
        updates.robot = state.robot ? { ...state.robot, mode: 'PICKUP' } : null;
      }
    }
    return updates;
  }),

  endSession: () => {
    const { currentSessionId } = get();
    if (currentSessionId) sessionApi.end(currentSessionId).catch(() => {});
    set({ sessionState: 'NO_SESSION', robot: null, session: { type: 'TIME', duration: 120, remainingTime: 7200, startedAt: null }, taskMission: null, guideQueue: [], followMe: { active: false, tagNumber: 11, status: 'STOPPED' }, pickupOrder: null, currentSessionId: null, currentRobotId: null, matchPin: null });
  },

  setRobotMode: (mode) => set((s) => ({ robot: s.robot ? { ...s.robot, mode } : null })),
  updateRemainingTime: (seconds) => set((s) => ({ session: { ...s.session, remainingTime: seconds } })),
  setTaskMission: (mission) => set({ taskMission: mission }),
  completeTaskSession: () => set({ sessionState: 'ENDED' }),

  /* ───── Guide ───── */

  addToGuideQueue: (poi) => {
    set((s) => ({ guideQueue: [...s.guideQueue, { id: `guide-${Date.now()}`, poiId: poi.id, poiName: poi.name, floor: 'Level 1', estimatedTime: Math.floor(Math.random() * 5) + 2, status: 'PENDING', selected: true }] }));
    const { currentSessionId } = get();
    if (currentSessionId) guideApi.addToQueue(currentSessionId, Number(poi.id)).catch(() => {});
  },
  removeFromGuideQueue: (id) => {
    set((s) => ({ guideQueue: s.guideQueue.filter((i) => i.id !== id) }));
    const { currentSessionId } = get();
    if (currentSessionId && !isNaN(Number(id))) guideApi.removeFromQueue(currentSessionId, Number(id)).catch(() => {});
  },
  toggleGuideSelection: (id) => set((s) => ({ guideQueue: s.guideQueue.map((i) => i.id === id ? { ...i, selected: !i.selected } : i) })),
  clearGuideQueue: () => {
    set({ guideQueue: [] });
    const { currentSessionId } = get();
    if (currentSessionId) guideApi.clear(currentSessionId).catch(() => {});
  },
  startGuide: () => {
    set((s) => {
      const f = s.guideQueue.find((i) => i.selected && i.status === 'PENDING');
      if (!f) return s;
      return { guideQueue: s.guideQueue.map((i) => i.id === f.id ? { ...i, status: 'IN_PROGRESS' } : i), robot: s.robot ? { ...s.robot, mode: 'GUIDE' } : null };
    });
    const { currentSessionId } = get();
    if (currentSessionId) guideApi.execute(currentSessionId).catch(() => {});
  },
  completeCurrentGuide: () => set((s) => {
    const cur = s.guideQueue.find((i) => i.status === 'IN_PROGRESS');
    if (!cur) return s;
    const updated = s.guideQueue.map((i) => i.id === cur.id ? { ...i, status: 'DONE' as GuideStatus } : i);
    const nxt = updated.find((i) => i.selected && i.status === 'PENDING');
    return { guideQueue: nxt ? updated.map((i) => i.id === nxt.id ? { ...i, status: 'IN_PROGRESS' as GuideStatus } : i) : updated };
  }),
  _setGuideQueueFromServer: (queue) => set({ guideQueue: queue }),

  /* ───── Follow ───── */

  startFollowMe: (tagNumber) => {
    set((s) => ({ followMe: { active: true, tagNumber, status: 'FOLLOWING' }, robot: s.robot ? { ...s.robot, mode: 'FOLLOW' } : null }));
    const { currentSessionId } = get();
    if (currentSessionId) sessionApi.setFollowTag(currentSessionId, tagNumber).catch(() => {});
  },
  stopFollowMe: () => set((s) => ({ followMe: { ...s.followMe, active: false, status: 'STOPPED' }, robot: s.robot ? { ...s.robot, mode: null } : null })),
  setFollowStatus: (status) => set((s) => ({ followMe: { ...s.followMe, status } })),

  /* ───── Pickup ───── */

  createPickupOrder: (storeId, items) => {
    const state = get();
    const store = state.stores.find((s) => s.id === storeId);
    const emptySlot = state.lockboxSlots.find(s => s.status === 'EMPTY');
    if (!emptySlot) return;
    const orderId = `#${Math.floor(1000 + Math.random() * 9000)}`;
    set({
      pickupOrder: { orderId, storeId, storeName: store?.name || 'Unknown Store', items, status: 'IDLE', meetupLocation: null, slotId: emptySlot.slotNumber },
      lockboxSlots: state.lockboxSlots.map(slot => slot.slotNumber === emptySlot.slotNumber ? { ...slot, status: 'RESERVED' as LockboxStatus, orderInfo: { orderId, storeName: store?.name || 'Unknown Store', customerName: state.userName } } : slot),
    });
    if (state.currentSessionId) pickupApi.create(state.currentSessionId, { pickup_poi_id: Number(storeId), created_channel: 'APP', items: items.map((it, i) => ({ product_id: i + 1, qty: it.quantity, unit_price: it.price })) }).catch(() => {});
  },
  setPickupStatus: (status) => set((s) => {
    const u: Partial<AppState> = {
      pickupOrder: s.pickupOrder ? { ...s.pickupOrder, status } : null,
      robot: s.robot ? { ...s.robot, mode: status !== 'DONE' && status !== 'IDLE' ? 'PICKUP' : s.robot.mode } : null,
    };
    if (status === 'RETURNING' && s.pickupOrder?.slotId)
      u.lockboxSlots = s.lockboxSlots.map(slot => slot.slotNumber === s.pickupOrder!.slotId ? { ...slot, status: 'PICKED_UP' as LockboxStatus, occupiedSince: new Date().toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) } : slot);
    return u;
  }),
  setMeetupLocation: (location) => set((s) => ({ pickupOrder: s.pickupOrder ? { ...s.pickupOrder, meetupLocation: location } : null })),

  /* ───── Lockbox ───── */

  openSlot: (slotNumber) => {
    const { currentRobotId } = get();
    set((s) => ({ lockboxLogs: [{ id: `log-${Date.now()}`, timestamp: new Date(), slotNumber, action: 'OPENED' as const, result: 'SUCCESS' as const, description: 'Slot opened successfully' }, ...s.lockboxLogs].slice(0, 10) }));
    if (currentRobotId) lockboxApi.openSlot(currentRobotId, slotNumber).catch(() => {});
  },
  confirmSlotFull: (slotNumber) => {
    set((s) => ({
      lockboxSlots: s.lockboxSlots.map((sl) => sl.slotNumber === slotNumber ? { ...sl, status: 'FULL', occupiedSince: new Date().toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) } : sl),
      lockboxLogs: [{ id: `log-${Date.now()}`, timestamp: new Date(), slotNumber, action: 'SECURED' as const, result: 'SUCCESS' as const, description: 'Items securely stored' }, ...s.lockboxLogs].slice(0, 10),
    }));
  },
  confirmSlotEmpty: (slotNumber) => set((s) => ({ lockboxSlots: s.lockboxSlots.map((sl) => sl.slotNumber === slotNumber ? { ...sl, status: 'EMPTY', occupiedSince: undefined, orderInfo: undefined } : sl) })),

  /* ───── Timer ───── */

  tickTimer: () => set((s) => {
    if (s.sessionState !== 'ACTIVE' || s.session.type !== 'TIME') return s;
    return { session: { ...s.session, remainingTime: Math.max(0, s.session.remainingTime - 1) } };
  }),
  tickApproachingEta: () => set((s) => {
    if (s.sessionState !== 'APPROACHING') return s;
    if (s.approachingEta <= 1) return { approachingEta: 0, sessionState: 'PIN_MATCHING' };
    return { approachingEta: s.approachingEta - 1 };
  }),

  /* ───── Shopping list ───── */

  toggleProductComplete: (id) => set((s) => ({ shoppingList: s.shoppingList.map((p) => p.id === id ? { ...p, completed: !p.completed } : p) })),
  addToShoppingList: (product) => set((s) => ({ shoppingList: [...s.shoppingList, { ...product, id: `product-${Date.now()}`, completed: false }] })),
  removeFromShoppingList: (id) => set((s) => ({ shoppingList: s.shoppingList.filter((p) => p.id !== id) })),

  /* ───── Search ───── */

  setSearchOpen: (open) => set((s) => ({ searchState: { ...s.searchState, isOpen: open } })),
  setSearchQuery: (query) => set((s) => {
    const filtered = s.stores.filter((st) => (st.name.toLowerCase().includes(query.toLowerCase()) || st.category.toLowerCase().includes(query.toLowerCase())) && (s.searchState.filter === 'All' || st.category.toLowerCase().includes(s.searchState.filter.toLowerCase())));
    return { searchState: { ...s.searchState, query, results: filtered } };
  }),
  setSearchFilter: (filter) => set((s) => {
    const filtered = s.stores.filter((st) => (st.name.toLowerCase().includes(s.searchState.query.toLowerCase()) || st.category.toLowerCase().includes(s.searchState.query.toLowerCase())) && (filter === 'All' || st.category.toLowerCase().includes(filter.toLowerCase())));
    return { searchState: { ...s.searchState, filter, results: filtered } };
  }),

  /* ───── WS-driven ───── */

  _updateRobotState: (data) => set((s) => {
    if (!s.robot) return s;
    return { robot: { ...s.robot, battery: data.battery_pct ?? s.robot.battery, location: { x: data.x_m ?? s.robot.location.x, y: data.y_m ?? s.robot.location.y } } };
  }),
}));
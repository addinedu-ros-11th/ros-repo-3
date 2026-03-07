import { create } from 'zustand';
import { sessionApi } from '@/api/sessions';
import { guideApi } from '@/api/guide';
import { pickupApi, lockboxApi, storeApi, poiApi, type PoiRes, type StoreRes, type LockboxSlotRes } from '@/api/services';
import { storeProducts as hardcodedStoreProducts } from '@/data/storeProducts';

export type SessionState = 'NO_SESSION' | 'FINDING_ROBOT' | 'ROBOT_ASSIGNED' | 'APPROACHING' | 'PIN_MATCHING' | 'ACTIVE' | 'ENDED';
export type RobotMode = 'GUIDE' | 'FOLLOW' | 'PICKUP' | null;
export type SessionType = 'TASK' | 'TIME';
export type GuideStatus = 'PENDING' | 'IN_PROGRESS' | 'ARRIVED' | 'DONE';
export type FollowStatus = 'FOLLOWING' | 'LOST' | 'STOPPED' | 'RECONNECTING';
export type PickupStatus = 'IDLE' | 'MOVING' | 'LOADING' | 'LOADED' | 'MEETUP_SET' | 'RETURNING' | 'DONE';
export type LockboxStatus = 'FULL' | 'EMPTY' | 'RESERVED' | 'PICKEDUP';
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
  items?: { name: string; quantity: number; price: number; productId?: number }[];
}

export interface GuideDestination {
  id: string;
  serverItemId: number | null;  // 서버 guide_queue_item.id (DELETE/PATCH용)
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
  orderId: string;       // 표시용: "#1234"
  serverOrderId: number | null;  // 서버 DB id (meetup API 호출용)
  storeId: string;
  storeName: string;
  items: { name: string; quantity: number; price: number }[];
  status: PickupStatus;
  meetupLocation: string | null;
  slotId: number | null;
}

export interface LockboxSlot {
  number: number;
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
  slug: string;
  poi_id: number;
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
  map_x?: number | null;
  map_y?: number | null;
  waitPoint: { x: number; y: number };
  category: string;
}

interface AppState {
  userName: string;
  userPhone: string;

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
  storeProducts: Record<string, { name: string; option: string; price: number; productId: number }[]>;

  initFromServer: () => Promise<void>;

  setUserName: (name: string) => void;
  startFindingRobot: (type: SessionType, duration: number) => void;
  assignRobot: (robot: Robot) => void;
  startPinMatching: () => void;
  activateSession: () => void;
  endSession: () => void;
  _resetOnSessionEnded: () => void;
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

  createPickupOrder: (storeId: string, items: { name: string; quantity: number; price: number; productId?: number }[]) => void;
  setPickupStatus: (status: PickupStatus) => void;
  setMeetupLocation: (location: string) => void;

  openSlot: (slotNumber: number) => void;
  confirmSlotFull: (slotNumber: number) => void;
  confirmSlotEmpty: (slotNumber: number) => void;
  initLockboxSlots: (robotId: number) => void;
  _setLockboxSlotsFromServer: (slots: LockboxSlotRes[]) => void;
  _onLockboxOpened: (slotNumber: number) => void;

  tickTimer: () => void;
  tickApproachingEta: () => void;

  toggleProductComplete: (id: string) => void;
  addToShoppingList: (product: Omit<Product, 'id' | 'completed'>) => void;
  removeFromShoppingList: (id: string) => void;

  setSearchOpen: (open: boolean) => void;
  setSearchQuery: (query: string) => void;
  setSearchFilter: (filter: string) => void;

  _setGuideQueueFromServer: (queue: GuideDestination[]) => void;
  _updateRobotState: (data: { battery_pct?: number; x_m?: number; y_m?: number }) => void;
}

/* ───── fallback data ───── */

const initialStores: Store[] = [
  { id: '1', slug: 'zara',        poi_id: 1, name: 'Zara',             category: 'Fashion & Apparel',  location: 'Level 2, Zone B', icon: 'checkroom',        open: true,  closeTime: '10:00 PM' },
  { id: '2', slug: 'nike',        poi_id: 2, name: 'Nike',             category: 'Sports & Outdoor',   location: 'Level 1, Zone A', icon: 'sports_basketball', open: true,  closeTime: '9:00 PM'  },
  { id: '3', slug: 'apple',       poi_id: 3, name: 'Apple',            category: 'Electronics',        location: 'Level 2, Zone C', icon: 'laptop_mac',       open: true,  closeTime: '9:30 PM'  },
  { id: '4', slug: 'intersport',  poi_id: 4, name: 'Intersport',       category: 'Sports & Outdoor',   location: 'Level 2, Zone B', icon: 'sports_basketball', open: true,  closeTime: '9:00 PM'  },
  { id: '5', slug: 'sportstyle',  poi_id: 5, name: 'SportyStyle',      category: 'Fashion & Apparel',  location: 'Level 1, Zone A', icon: 'checkroom',        open: true,  closeTime: '10:00 PM' },
  { id: '6', slug: 'progym',      poi_id: 6, name: 'ProGym Equipment', category: 'Fitness',            location: 'Ground Floor',    icon: 'fitness_center',   open: false, closeTime: '9:00 PM'  },
  { id: '7', slug: 'starbucks',   poi_id: 7, name: 'Starbucks',        category: 'Dining',             location: 'Level 1, Zone B', icon: 'local_cafe',       open: true,  closeTime: '11:00 PM' },
  { id: '8', slug: 'hm',          poi_id: 8, name: 'H&M',              category: 'Fashion & Apparel',  location: 'Level 1, Zone C', icon: 'checkroom',        open: true,  closeTime: '9:00 PM'  },
];

const initialPOIs: POI[] = [
  { id: 1, name: 'Zara', x: 40, y: 90, waitPoint: { x: 38, y: 88 }, category: 'Fashion' },
  { id: 2, name: 'Nike', x: 280, y: 80, waitPoint: { x: 278, y: 78 }, category: 'Sports' },
  { id: 3, name: 'Apple', x: 160, y: 30, waitPoint: { x: 158, y: 28 }, category: 'Electronics' },
  { id: 7, name: 'Starbucks', x: 120, y: 150, waitPoint: { x: 118, y: 148 }, category:'Dining' },
  { id: 8, name: 'H&M', x: 220, y: 120, waitPoint: { x: 218, y: 118 }, category:'Fashion'},
  { id: 4, name: 'Intersport', x: 300, y: 140, waitPoint: { x: 298, y: 138 }, category: 'Sports' },
  { id: 5, name: 'SportyStyle', x: 60, y: 150, waitPoint: { x: 58, y: 148 }, category: 'Fashion' },
  { id: 6, name: 'ProGym Equipment', x: 200, y: 40, waitPoint: { x: 198, y: 38 }, category: 'Fitness' },
];


const initialShoppingList: Product[] = [
  { id: '1', storeId: 'zara', name: 'Linen Blend Shirt', option: 'Size M, Beige', price: 45.90, completed: false },
  { id: '2', storeId: 'zara', name: 'Pleated Trousers', option: 'Size 32, Black', price: 59.90, completed: true },
  { id: '3', storeId: 'nike', name: 'Air Zoom Pegasus', option: 'Size 10, Grey/Volt', price: 120.00, completed: false },
  { id: '4', storeId: 'nike', name: 'Running Socks (3pk)', option: 'White', price: 18.00, completed: false },
  { id: '5', storeId: 'nike', name: 'Dri-FIT Headband', option: 'Black', price: 12.00, completed: true },
  { id: '6', storeId: 'apple', name: 'USB-C Charge Cable', option: '2m', price: 19.00, completed: false },
  // { id: '7', storeId: 'starbucks', name: 'Tumbler', option: 'Grande, Green', price: 24.00, completed: false },
  { id: '8', storeId: 'hm', name: 'Basic T-Shirt', option: 'Size L, White', price: 9.99, completed: false },
];

/* ───── server → frontend mapping ───── */

const catIcon: Record<string, string> = {
  fashion: 'checkroom', sports: 'sports_basketball', electronics: 'laptop_mac',
  cafe: 'local_cafe', fitness: 'fitness_center', dining: 'local_cafe',
};
function mapStore(s: StoreRes): Store {
  const c = (s.category || 'other').toLowerCase();
  const slug = (s.name || '').toLowerCase().replace(/[^a-z0-9]/g, '');
  return { id: String(s.id), slug, poi_id: s.poi_id, name: s.name || `Store #${s.id}`, category: s.category || 'Other',
    location: `(${s.x_m?.toFixed(0) ?? 0}, ${s.y_m?.toFixed(0) ?? 0})`,
    icon: catIcon[c] || 'store', open: true, closeTime: '9:00 PM' };
}
function mapPoi(p: PoiRes): POI {
  return { 
    id: p.id, name: p.name, 
    x: p.x_m, y: p.y_m,
    map_x: p.map_x_m,
    map_y: p.map_y_m,
    waitPoint: { x: p.wait_x_m ?? p.x_m - 2, y: p.wait_y_m ?? p.y_m - 2 },
    category: p.type || 'OTHER'
  };
}

/* 빈 슬롯 5개 — UI 기본 골격 (서버 데이터 로드 전 표시용, 세션 종료 시 복원) */
const initialLockboxSlots: LockboxSlot[] = [
  { number: 1, status: 'EMPTY' },
  { number: 2, status: 'EMPTY' },
  { number: 3, status: 'EMPTY' },
  { number: 4, status: 'EMPTY' },
  { number: 5, status: 'EMPTY' },
];

/* localId 충돌 방지용 카운터 (Date.now()는 동기 루프에서 중복됨) */
let _guideLocalSeq = 0;

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
  lockboxLogs: [],
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

      if (sr?.length) {
        const productsMap: Record<string, { name: string; option: string; price: number; productId: number }[]> = {};
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
              productId: p.id,
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
    set({ sessionState: 'FINDING_ROBOT', session: { type, duration, remainingTime: duration * 60, startedAt: null }, approachingEta: 10 });
    sessionApi.create({ user_id: 1, session_type: type, requested_minutes: type === 'TIME' ? duration : undefined })
      .then((res) => {
        set({ currentSessionId: res.id, matchPin: res.match_pin });
        if (res.assigned_robot_id) {
          set({
            currentRobotId: res.assigned_robot_id,
            sessionState: 'APPROACHING',
            robot: {
              id: String(res.assigned_robot_id),
              name: `Mall·E-${res.assigned_robot_id}`,
              battery: 80,
              mode: null,
              location: { x: 0, y: 0 },
            },
          });
        }
      }).catch((e) => {
        console.error('[API] session create:', e);
        set({ sessionState: 'NO_SESSION' });
      });
  },

  assignRobot: (robot) => set({ sessionState: 'APPROACHING', robot: { ...robot, name: robot.name.replace('PinkyPro', 'Mall·E') } }),
  startPinMatching: () => set({ sessionState: 'PIN_MATCHING', approachingEta: 0 }),

  activateSession: async () => {
    const state = get();
    const updates: Partial<AppState> = { sessionState: 'ACTIVE', session: { ...state.session, startedAt: new Date() } };
    if (state.session.type === 'TASK' && state.taskMission) {
      if (state.taskMission.type === 'GUIDE' && state.taskMission.destinationPoi) {
        const poi = state.taskMission.destinationPoi;
        updates.guideQueue = [{
          id: `guide-task-${Date.now()}`,
          serverItemId: null,
          poiId: poi.id,
          poiName: poi.name,
          floor: 'Level 1',
          estimatedTime: Math.floor(Math.random() * 5) + 2,
          status: 'PENDING',
          selected: true,
        }];
        updates.robot = state.robot ? { ...state.robot, mode: 'GUIDE' } : null;
        set(updates);
        if (state.currentSessionId) {
          await guideApi.addToQueue(state.currentSessionId, Number(poi.id)).catch(() => {});
          await guideApi.execute(state.currentSessionId).catch(() => {});
        }
        return;
      } else if (state.taskMission.type === 'PICKUP' && state.taskMission.storeId && state.taskMission.items) {
        const store = state.stores.find(s => s.id === state.taskMission!.storeId);
        const orderId = `#${Math.floor(1000 + Math.random() * 9000)}`;
        // 로컬 pickupOrder 상태만 설정 — lockbox RESERVED는 서버 API → WS LOCKBOX_UPDATED로 동기화
        updates.pickupOrder = { orderId, serverOrderId: null, storeId: state.taskMission.storeId, storeName: store?.name || state.taskMission.storeName || 'Unknown Store', items: state.taskMission.items, status: 'MOVING', meetupLocation: null, slotId: null };
        updates.robot = state.robot ? { ...state.robot, mode: 'PICKUP' } : null;
      }
    }
    set(updates);
  },

  endSession: () => {
    const { currentSessionId } = get();
    if (currentSessionId) sessionApi.end(currentSessionId).catch(() => {});
    set({ sessionState: 'NO_SESSION', robot: null, session: { type: 'TIME', duration: 120, remainingTime: 7200, startedAt: null }, taskMission: null, guideQueue: [], followMe: { active: false, tagNumber: 11, status: 'STOPPED' }, pickupOrder: null, currentSessionId: null, currentRobotId: null, matchPin: null, lockboxSlots: initialLockboxSlots, lockboxLogs: [] });
  },

  // WS SESSION_ENDED 수신 시 사용 — API 재호출 없이 상태만 초기화
  _resetOnSessionEnded: () => {
    set({ sessionState: 'NO_SESSION', robot: null, session: { type: 'TIME', duration: 120, remainingTime: 7200, startedAt: null }, taskMission: null, guideQueue: [], followMe: { active: false, tagNumber: 11, status: 'STOPPED' }, pickupOrder: null, currentSessionId: null, currentRobotId: null, matchPin: null, lockboxSlots: initialLockboxSlots, lockboxLogs: [] });
  },

  setRobotMode: (mode) => set((s) => ({ robot: s.robot ? { ...s.robot, mode } : null })),
  updateRemainingTime: (seconds) => set((s) => ({ session: { ...s.session, remainingTime: seconds } })),
  setTaskMission: (mission) => set({ taskMission: mission }),
  completeTaskSession: () => set({ sessionState: 'ENDED' }),

  /* ───── Guide ───── */

  addToGuideQueue: (poi) => {
    const localId = `guide-local-${++_guideLocalSeq}`;
    // 낙관적 UI 업데이트 (serverItemId는 API 응답 후 채움)
    set((s) => ({
      guideQueue: [...s.guideQueue, {
        id: localId,
        serverItemId: null,
        poiId: String(poi.id),
        poiName: poi.name,
        floor: 'Level 1',
        estimatedTime: Math.floor(Math.random() * 5) + 2,
        status: 'PENDING',
        selected: true,
      }]
    }));
    const { currentSessionId } = get();
    if (currentSessionId) {
      guideApi.addToQueue(currentSessionId, poi.id)
        .then((res) => {
          // 서버 item id를 localId로 찾아서 업데이트
          set((s) => ({
            guideQueue: s.guideQueue.map((i) =>
              i.id === localId ? { ...i, serverItemId: res.id } : i
            )
          }));
        })
        .catch(() => {});
    }
  },

  removeFromGuideQueue: (id) => {
    // 삭제 전에 serverItemId 먼저 조회
    const item = get().guideQueue.find((i) => i.id === id);
    set((s) => ({ guideQueue: s.guideQueue.filter((i) => i.id !== id) }));
    const { currentSessionId } = get();
    if (currentSessionId && item?.serverItemId) {
      guideApi.removeFromQueue(currentSessionId, item.serverItemId).catch(() => {});
    }
  },

  toggleGuideSelection: (id) => set((s) => ({
    guideQueue: s.guideQueue.map((i) => i.id === id ? { ...i, selected: !i.selected } : i)
  })),

  clearGuideQueue: () => {
    set({ guideQueue: [] });
    const { currentSessionId } = get();
    if (currentSessionId) guideApi.clear(currentSessionId).catch(() => {});
  },

  startGuide: () => {
      set((s) => {
        const f = s.guideQueue.find((i) => i.selected && i.status === 'PENDING');
        if (!f) return s;
        return {
          guideQueue: s.guideQueue.map((i) => i.id === f.id ? { ...i, status: 'IN_PROGRESS' as GuideStatus } : i),
          robot: s.robot ? { ...s.robot, mode: 'GUIDE' } : null,
        };
      });
      const { currentSessionId } = get();
      if (currentSessionId) {
        guideApi.execute(currentSessionId)
          .then((res) => console.log('[Guide] execute OK:', res))  // ← 추가
          .catch((e) => console.error('[Guide] execute FAIL:', e)); // ← 추가
      }
    },

  completeCurrentGuide: () => set((s) => {
    const cur = s.guideQueue.find((i) => i.status === 'IN_PROGRESS');
    if (!cur) return s;
    const updated = s.guideQueue.map((i) => i.id === cur.id ? { ...i, status: 'DONE' as GuideStatus } : i);
    const nxt = updated.find((i) => i.selected && i.status === 'PENDING');
    return { guideQueue: nxt ? updated.map((i) => i.id === nxt.id ? { ...i, status: 'IN_PROGRESS' as GuideStatus } : i) : updated };
  }),

  _setGuideQueueFromServer: (serverQueue) => set((s) => {
    // 서버 큐에 이미 반영된 poiId 집합
    const serverPoiIds = new Set(serverQueue.map((i) => i.poiId));

    // serverItemId === null이고, 서버 큐에 없는 poiId의 낙관적 항목만 유지
    // (WS가 API 응답보다 먼저 도착해도 같은 poiId가 중복되지 않음)
    const pendingOptimistic = s.guideQueue.filter(
      (i) => i.serverItemId === null && !serverPoiIds.has(i.poiId)
    );

    // 서버 큐 항목에 기존 선택 상태 병합 (사용자가 선택한 상태 보존)
    const mergedServerItems = serverQueue.map((serverItem) => {
      const existing = s.guideQueue.find((i) => i.serverItemId === serverItem.serverItemId);
      return existing ? { ...serverItem, selected: existing.selected } : serverItem;
    });

    return { guideQueue: [...mergedServerItems, ...pendingOptimistic] };
  }),

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
      pickupOrder: { orderId, serverOrderId: null, storeId, storeName: store?.name || 'Unknown Store', items, status: 'IDLE', meetupLocation: null, slotId: 0 },
    });
    if (state.currentSessionId) {
      pickupApi.create(state.currentSessionId, {
        pickup_poi_id: store?.poi_id ?? Number(storeId),
        created_channel: 'APP',
        items: items.map((it) => ({
            product_id: it.productId ?? 0,  // ← i + 1 대신
            qty: it.quantity,
            unit_price: it.price,
        })),
      }).then((res) => {
        // 서버 ID 저장 (meetup API 호출용)
        useAppStore.setState((s) => ({
          pickupOrder: s.pickupOrder ? { ...s.pickupOrder, serverOrderId: res.id } : null,
        }));
      }).catch(() => {});
    }
  },
  setPickupStatus: (status) => set((s) => ({
    pickupOrder: s.pickupOrder ? { ...s.pickupOrder, status } : null,
    robot: s.robot ? { ...s.robot, mode: status === 'DONE' ? null : status !== 'IDLE' ? 'PICKUP' : s.robot.mode } : null,
  })),
  setMeetupLocation: (location) => set((s) => ({ pickupOrder: s.pickupOrder ? { ...s.pickupOrder, meetupLocation: location } : null })),

  /* ───── Lockbox ───── */

  openSlot: (slotNumber) => {
    const { currentRobotId } = get();
    set((s) => ({ lockboxLogs: [{ id: `log-${Date.now()}`, timestamp: new Date(), slotNumber, action: 'OPENED' as const, result: 'SUCCESS' as const, description: 'Slot opened successfully' }, ...s.lockboxLogs].slice(0, 10) }));
    if (currentRobotId) lockboxApi.openSlot(currentRobotId, slotNumber).catch(() => {});
  },
  confirmSlotFull: (slotNumber) => {
    const now = new Date();
    set((s) => ({
      lockboxSlots: s.lockboxSlots.map((sl) => sl.number === slotNumber ? { ...sl, status: 'FULL' as LockboxStatus, occupiedSince: now.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) } : sl),
      lockboxLogs: [{ id: `log-${now.getTime()}`, timestamp: now, slotNumber, action: 'SECURED' as const, result: 'SUCCESS' as const, description: 'Items securely stored' }, ...s.lockboxLogs].slice(0, 10),
    }));
    const { currentRobotId } = get();
    if (currentRobotId) lockboxApi.updateSlotStatus(currentRobotId, slotNumber, 'FULL').catch(() => {});
  },
  confirmSlotEmpty: (slotNumber) => {
    set((s) => ({ lockboxSlots: s.lockboxSlots.map((sl) => sl.number === slotNumber ? { ...sl, status: 'EMPTY' as LockboxStatus, occupiedSince: undefined, orderInfo: undefined } : sl) }));
    const { currentRobotId } = get();
    if (currentRobotId) lockboxApi.updateSlotStatus(currentRobotId, slotNumber, 'EMPTY').catch(() => {});
  },

  initLockboxSlots: (robotId) => {
    lockboxApi.getSlots(robotId)
      .then((slots) => useAppStore.getState()._setLockboxSlotsFromServer(slots))
      .catch(() => {});
  },

  _setLockboxSlotsFromServer: (serverSlots) => set((s) => ({
    lockboxSlots: serverSlots.map((sl) => {
      const existing = s.lockboxSlots.find((e) => e.number === sl.slot_no);
      let newOrderInfo = existing?.orderInfo;
      if (sl.order_id != null) {
        newOrderInfo = {
          orderId: `#${sl.order_id}`,
          storeName: sl.store_name ?? existing?.orderInfo?.storeName ?? `Order #${sl.order_id}`,
          customerName: existing?.orderInfo?.customerName ?? s.userName,
        };
      }
      return {
        number: sl.slot_no,
        status: sl.status as LockboxStatus,
        occupiedSince: existing?.occupiedSince,
        orderInfo: newOrderInfo,
      };
    }),
  })),

  _onLockboxOpened: (slotNumber) => set((s) => ({
    lockboxLogs: [
      { id: `log-${Date.now()}`, timestamp: new Date(), slotNumber, action: 'OPENED' as const, result: 'SUCCESS' as const, description: `Slot ${slotNumber} opened` },
      ...s.lockboxLogs,
    ].slice(0, 10),
  })),

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
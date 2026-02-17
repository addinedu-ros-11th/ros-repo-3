import { create } from 'zustand';

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
  // Guide mission
  destinationPoi?: POI;
  // Pickup mission
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
  // User
  userName: string;
  userPhone: string;

  // Session
  sessionState: SessionState;
  robot: Robot | null;
  session: Session;
  taskMission: TaskMission | null;
  approachingEta: number;

  // Modes
  guideQueue: GuideDestination[];
  followMe: FollowMeState;
  pickupOrder: PickupOrder | null;

  // Lockbox
  lockboxSlots: LockboxSlot[];
  lockboxLogs: LockboxLog[];

  // Shopping List
  shoppingList: Product[];

  // Search
  searchState: SearchState;

  // Data
  stores: Store[];
  pois: POI[];

  // Actions
  setUserName: (name: string) => void;
  startFindingRobot: (type: SessionType, duration: number) => void;
  assignRobot: (robot: Robot) => void;
  startPinMatching: () => void;
  activateSession: () => void;
  endSession: () => void;
  setRobotMode: (mode: RobotMode) => void;
  updateRemainingTime: (seconds: number) => void;

  // Task mission actions
  setTaskMission: (mission: TaskMission) => void;
  completeTaskSession: () => void;

  // Guide actions
  addToGuideQueue: (poi: POI) => void;
  removeFromGuideQueue: (id: string) => void;
  toggleGuideSelection: (id: string) => void;
  clearGuideQueue: () => void;
  startGuide: () => void;
  completeCurrentGuide: () => void;

  // Follow actions
  startFollowMe: (tagNumber: 11 | 12 | 13) => void;
  stopFollowMe: () => void;
  setFollowStatus: (status: FollowStatus) => void;

  // Pickup actions
  createPickupOrder: (storeId: string, items: { name: string; quantity: number; price: number }[]) => void;
  setPickupStatus: (status: PickupStatus) => void;
  setMeetupLocation: (location: string) => void;

  // Lockbox actions
  openSlot: (slotNumber: number) => void;
  confirmSlotFull: (slotNumber: number) => void;
  confirmSlotEmpty: (slotNumber: number) => void;

  // Timer
  tickTimer: () => void;
  tickApproachingEta: () => void;

  // Shopping list actions
  toggleProductComplete: (id: string) => void;
  addToShoppingList: (product: Omit<Product, 'id' | 'completed'>) => void;
  removeFromShoppingList: (id: string) => void;

  // Search actions
  setSearchOpen: (open: boolean) => void;
  setSearchQuery: (query: string) => void;
  setSearchFilter: (filter: string) => void;
}

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

export const useAppStore = create<AppState>((set, get) => ({
  // Initial state
  userName: 'Sarah',
  userPhone: '+1 (555) 123-4567',

  sessionState: 'NO_SESSION',
  robot: null,
  session: {
    type: 'TIME',
    duration: 120,
    remainingTime: 7200,
    startedAt: null,
  },
  taskMission: null,
  approachingEta: 10,

  guideQueue: [],
  followMe: { active: false, tagNumber: 11, status: 'STOPPED' },
  pickupOrder: null,

  lockboxSlots: initialLockboxSlots,
  lockboxLogs: initialLockboxLogs,

  shoppingList: initialShoppingList,

  searchState: {
    query: '',
    filter: 'All',
    results: initialStores,
    isOpen: false,
  },

  stores: initialStores,
  pois: initialPOIs,

  // Actions
  setUserName: (name) => set({ userName: name }),

  startFindingRobot: (type, duration) => set({
    sessionState: 'FINDING_ROBOT',
    session: { type, duration, remainingTime: duration * 60, startedAt: null },
    approachingEta: 10,
  }),

  assignRobot: (robot) => set({
    sessionState: 'APPROACHING',
    robot: { ...robot, name: robot.name.replace('PinkyPro', 'Mall·E') },
  }),

  startPinMatching: () => set({ sessionState: 'PIN_MATCHING', approachingEta: 0 }),

  activateSession: () => set((state) => {
    const updates: Partial<AppState> = {
      sessionState: 'ACTIVE',
      session: { ...state.session, startedAt: new Date() },
    };

    // Auto-setup for TASK mode
    if (state.session.type === 'TASK' && state.taskMission) {
      if (state.taskMission.type === 'GUIDE' && state.taskMission.destinationPoi) {
        const poi = state.taskMission.destinationPoi;
        updates.guideQueue = [{
          id: `guide-task-${Date.now()}`,
          poiId: poi.id,
          poiName: poi.name,
          floor: 'Level 1',
          estimatedTime: Math.floor(Math.random() * 5) + 2,
          status: 'PENDING',
          selected: true,
        }];
        updates.robot = state.robot ? { ...state.robot, mode: 'GUIDE' } : null;
      } else if (state.taskMission.type === 'PICKUP' && state.taskMission.storeId && state.taskMission.items) {
        const store = state.stores.find(s => s.id === state.taskMission!.storeId);
        const emptySlot = state.lockboxSlots.find(s => s.status === 'EMPTY');
        const orderId = `#${Math.floor(1000 + Math.random() * 9000)}`;
        updates.pickupOrder = {
          orderId,
          storeId: state.taskMission.storeId,
          storeName: store?.name || state.taskMission.storeName || 'Unknown Store',
          items: state.taskMission.items,
          status: 'MOVING',
          meetupLocation: null,
          slotId: emptySlot?.slotNumber || null,
        };
        if (emptySlot) {
          updates.lockboxSlots = state.lockboxSlots.map(slot =>
            slot.slotNumber === emptySlot.slotNumber
              ? {
                  ...slot,
                  status: 'RESERVED' as LockboxStatus,
                  orderInfo: { orderId, storeName: store?.name || 'Unknown Store', customerName: state.userName },
                }
              : slot
          );
        }
        updates.robot = state.robot ? { ...state.robot, mode: 'PICKUP' } : null;
      }
    }

    return updates;
  }),

  endSession: () => set({
    sessionState: 'NO_SESSION',
    robot: null,
    session: { type: 'TIME', duration: 120, remainingTime: 7200, startedAt: null },
    taskMission: null,
    guideQueue: [],
    followMe: { active: false, tagNumber: 11, status: 'STOPPED' },
    pickupOrder: null,
  }),

  setRobotMode: (mode) => set((state) => ({
    robot: state.robot ? { ...state.robot, mode } : null,
  })),

  updateRemainingTime: (seconds) => set((state) => ({
    session: { ...state.session, remainingTime: seconds },
  })),

  // Task mission actions
  setTaskMission: (mission) => set({ taskMission: mission }),

  completeTaskSession: () => set({ sessionState: 'ENDED' }),

  // Guide actions
  addToGuideQueue: (poi) => set((state) => ({
    guideQueue: [...state.guideQueue, {
      id: `guide-${Date.now()}`,
      poiId: poi.id,
      poiName: poi.name,
      floor: 'Level 1',
      estimatedTime: Math.floor(Math.random() * 5) + 2,
      status: 'PENDING',
      selected: true,
    }],
  })),

  removeFromGuideQueue: (id) => set((state) => ({
    guideQueue: state.guideQueue.filter((item) => item.id !== id),
  })),

  toggleGuideSelection: (id) => set((state) => ({
    guideQueue: state.guideQueue.map((item) =>
      item.id === id ? { ...item, selected: !item.selected } : item
    ),
  })),

  clearGuideQueue: () => set({ guideQueue: [] }),

  startGuide: () => set((state) => {
    const firstSelected = state.guideQueue.find((item) => item.selected && item.status === 'PENDING');
    if (!firstSelected) return state;
    return {
      guideQueue: state.guideQueue.map((item) =>
        item.id === firstSelected.id ? { ...item, status: 'IN_PROGRESS' } : item
      ),
      robot: state.robot ? { ...state.robot, mode: 'GUIDE' } : null,
    };
  }),

  completeCurrentGuide: () => set((state) => {
    const currentGuide = state.guideQueue.find((item) => item.status === 'IN_PROGRESS');
    if (!currentGuide) return state;

    const updatedQueue = state.guideQueue.map((item) =>
      item.id === currentGuide.id ? { ...item, status: 'DONE' as GuideStatus } : item
    );

    const nextPending = updatedQueue.find((item) => item.selected && item.status === 'PENDING');

    return {
      guideQueue: nextPending
        ? updatedQueue.map((item) =>
            item.id === nextPending.id ? { ...item, status: 'IN_PROGRESS' as GuideStatus } : item
          )
        : updatedQueue,
    };
  }),

  // Follow actions
  startFollowMe: (tagNumber) => set((state) => ({
    followMe: { active: true, tagNumber, status: 'FOLLOWING' },
    robot: state.robot ? { ...state.robot, mode: 'FOLLOW' } : null,
  })),

  stopFollowMe: () => set((state) => ({
    followMe: { ...state.followMe, active: false, status: 'STOPPED' },
    robot: state.robot ? { ...state.robot, mode: null } : null,
  })),

  setFollowStatus: (status) => set((state) => ({
    followMe: { ...state.followMe, status },
  })),

  // Pickup actions
  createPickupOrder: (storeId, items) => {
    const state = get();
    const store = state.stores.find((s) => s.id === storeId);
    const emptySlot = state.lockboxSlots.find(s => s.status === 'EMPTY');
    if (!emptySlot) return; // Should not happen — UI blocks this
    const orderId = `#${Math.floor(1000 + Math.random() * 9000)}`;
    set({
      pickupOrder: {
        orderId,
        storeId,
        storeName: store?.name || 'Unknown Store',
        items,
        status: 'IDLE',
        meetupLocation: null,
        slotId: emptySlot.slotNumber,
      },
      lockboxSlots: state.lockboxSlots.map(slot =>
        slot.slotNumber === emptySlot.slotNumber
          ? {
              ...slot,
              status: 'RESERVED' as LockboxStatus,
              orderInfo: {
                orderId,
                storeName: store?.name || 'Unknown Store',
                customerName: state.userName,
              },
            }
          : slot
      ),
    });
  },

  setPickupStatus: (status) => set((state) => {
    const updates: Partial<AppState> = {
      pickupOrder: state.pickupOrder ? { ...state.pickupOrder, status } : null,
      robot: state.robot ? { ...state.robot, mode: status !== 'DONE' && status !== 'IDLE' ? 'PICKUP' : state.robot.mode } : null,
    };
    // When robot is returning with items loaded, mark slot as PICKED_UP
    if (status === 'RETURNING' && state.pickupOrder?.slotId) {
      updates.lockboxSlots = state.lockboxSlots.map(slot =>
        slot.slotNumber === state.pickupOrder!.slotId
          ? { ...slot, status: 'PICKED_UP' as LockboxStatus, occupiedSince: new Date().toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) }
          : slot
      );
    }
    return updates;
  }),

  setMeetupLocation: (location) => set((state) => ({
    pickupOrder: state.pickupOrder ? { ...state.pickupOrder, meetupLocation: location } : null,
  })),

  // Lockbox actions
  openSlot: (slotNumber) => {
    const newLog: LockboxLog = {
      id: `log-${Date.now()}`,
      timestamp: new Date(),
      slotNumber,
      action: 'OPENED',
      result: 'SUCCESS',
      description: 'Slot opened successfully',
    };
    set((state) => ({
      lockboxLogs: [newLog, ...state.lockboxLogs].slice(0, 10),
    }));
  },

  confirmSlotFull: (slotNumber) => {
    const newLog: LockboxLog = {
      id: `log-${Date.now()}`,
      timestamp: new Date(),
      slotNumber,
      action: 'SECURED',
      result: 'SUCCESS',
      description: 'Items securely stored',
    };
    set((state) => ({
      lockboxSlots: state.lockboxSlots.map((slot) =>
        slot.slotNumber === slotNumber
          ? { ...slot, status: 'FULL', occupiedSince: new Date().toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) }
          : slot
      ),
      lockboxLogs: [newLog, ...state.lockboxLogs].slice(0, 10),
    }));
  },

  confirmSlotEmpty: (slotNumber) => set((state) => ({
    lockboxSlots: state.lockboxSlots.map((slot) =>
      slot.slotNumber === slotNumber
        ? { ...slot, status: 'EMPTY', occupiedSince: undefined, orderInfo: undefined }
        : slot
    ),
  })),

  // Timer
  tickTimer: () => set((state) => {
    if (state.sessionState !== 'ACTIVE' || state.session.type !== 'TIME') return state;
    const next = Math.max(0, state.session.remainingTime - 1);
    return { session: { ...state.session, remainingTime: next } };
  }),

  tickApproachingEta: () => set((state) => {
    if (state.sessionState !== 'APPROACHING') return state;
    if (state.approachingEta <= 1) {
      return { approachingEta: 0, sessionState: 'PIN_MATCHING' };
    }
    return { approachingEta: state.approachingEta - 1 };
  }),

  // Shopping list actions
  toggleProductComplete: (id) => set((state) => ({
    shoppingList: state.shoppingList.map((product) =>
      product.id === id ? { ...product, completed: !product.completed } : product
    ),
  })),

  addToShoppingList: (product) => set((state) => ({
    shoppingList: [...state.shoppingList, { ...product, id: `product-${Date.now()}`, completed: false }],
  })),

  removeFromShoppingList: (id) => set((state) => ({
    shoppingList: state.shoppingList.filter((product) => product.id !== id),
  })),

  // Search actions
  setSearchOpen: (open) => set((state) => ({
    searchState: { ...state.searchState, isOpen: open },
  })),

  setSearchQuery: (query) => set((state) => {
    const filtered = state.stores.filter((store) => {
      const matchesQuery = store.name.toLowerCase().includes(query.toLowerCase()) ||
        store.category.toLowerCase().includes(query.toLowerCase());
      const matchesFilter = state.searchState.filter === 'All' ||
        store.category.toLowerCase().includes(state.searchState.filter.toLowerCase());
      return matchesQuery && matchesFilter;
    });
    return {
      searchState: { ...state.searchState, query, results: filtered },
    };
  }),

  setSearchFilter: (filter) => set((state) => {
    const filtered = state.stores.filter((store) => {
      const matchesQuery = store.name.toLowerCase().includes(state.searchState.query.toLowerCase()) ||
        store.category.toLowerCase().includes(state.searchState.query.toLowerCase());
      const matchesFilter = filter === 'All' ||
        store.category.toLowerCase().includes(filter.toLowerCase());
      return matchesQuery && matchesFilter;
    });
    return {
      searchState: { ...state.searchState, filter, results: filtered },
    };
  }),
}));

// Session and Robot Types
export type SessionState = 'INACTIVE' | 'ASSIGNED' | 'APPROACHING' | 'PIN_MATCHING' | 'ACTIVE' | 'ENDED';
export type RobotStatus = 'IDLE' | 'MOVING' | 'WAITING' | 'STOPPED';
export type NetworkStrength = 'Strong' | 'Weak' | 'Disconnected';
export type SessionType = 'TASK' | 'TIME' | null;
export type ActiveMode = 'GUIDE' | 'FOLLOW' | 'PICKUP' | null;

export interface Robot {
  id: string;
  name: string;
  battery: number;
  networkStrength: NetworkStrength;
  status: RobotStatus;
}

export interface Session {
  type: SessionType;
  remainingTime: number; // seconds
  customerId: string | null;
  customerName: string | null;
}

// Guide Mode Types
export type GuideQueueStatus = 'PENDING' | 'IN_PROGRESS' | 'ARRIVED' | 'DONE';

export interface GuideQueueItem {
  id: string;
  serverItemId: number | null;  // 서버 guide_queue_item.id (DELETE/PATCH용)
  poiId: string;
  poiName: string;
  floor: string;
  estimatedTime: number; // minutes
  status: GuideQueueStatus;
  selected: boolean;
}

export interface GuideState {
  queue: GuideQueueItem[];
  isExecuting: boolean;
  currentDestinationIndex: number;
}

// Follow Mode Types
export type FollowTag = 11 | 12 | 13 | null;
export type FollowStatus = 'FOLLOWING' | 'LOST' | 'STOPPED' | 'RECONNECTING';

export interface FollowState {
  active: boolean;
  tagNumber: FollowTag;
  status: FollowStatus;
}

// Pickup Mode Types
export type PickupStatus = 'MOVING' | 'ARRIVED' | 'STAFF_PIN' | 'LOADING' | 'LOADED' | 'MEETUP_SET' | 'RETURNING' | 'DONE';

export interface OrderItem {
  name: string;
  quantity: number;
  price: number;
  productId?: number;
}

export interface PickupOrder {
  orderId: string;
  serverOrderId?: number | null; // 서버 pickup_orders.id (status 업데이트용)
  storeName: string;
  items: OrderItem[];
  slotId: number;
  status: PickupStatus;
  meetupLocation: string | null;
}

export interface PickupState {
  currentOrder: PickupOrder | null;
  showLoadingOverlay: boolean;
}

// Lockbox Types
export type SlotStatus = 'FULL' | 'EMPTY' | 'RESERVED' | 'PICKEDUP';
export type LogAction = 'OPENED' | 'SECURED' | 'FAILED';
export type LogResult = 'SUCCESS' | 'FAILURE';

export interface OrderInfo {
  orderId: string;
  storeName: string;
  customerName: string;
}

export interface LockboxSlot {
  number: 1 | 2 | 3 | 4 | 5;
  status: SlotStatus;
  occupiedSince?: string;
  orderInfo?: OrderInfo;
  isPickupOrder?: boolean;
  pickedUp?: boolean;
}

export interface LockboxLog {
  id: string;
  timestamp: string;
  slotNumber: number;
  action: LogAction;
  result: LogResult;
  description: string;
}

// Notification Types
export type NotificationCategory = 'NAVIGATION' | 'LOCKBOX' | 'PICKUP' | 'SYSTEM';

export interface Notification {
  id: string;
  category: NotificationCategory;
  title: string;
  description: string;
  timestamp: Date;
  read: boolean;
}

// Store Types
export interface Store {
  id: string;
  name: string;
  category: string;
  location: string;
  icon: string;
  open: boolean;
}

export interface Product {
  id: string;
  name: string;
  price: number;
  storeId: string;
}

// Voice Intent Types
export type VoiceIntentType =
  | 'GUIDE_TO'
  | 'OPEN_LOCKBOX'
  | 'START_FOLLOW'
  | 'CREATE_PICKUP'
  | 'EMERGENCY_STOP'
  | 'RETURN_TO_STATION'
  | 'SHOW_STATUS'
  | 'UNKNOWN';

export type VoiceIntent =
  | { type: 'GUIDE_TO'; destination: string }
  | { type: 'OPEN_LOCKBOX'; slotId: number }
  | { type: 'START_FOLLOW'; tagId: number }
  | { type: 'CREATE_PICKUP'; storeName: string }
  | { type: 'EMERGENCY_STOP' }
  | { type: 'RETURN_TO_STATION' }
  | { type: 'SHOW_STATUS' }
  | { type: 'UNKNOWN'; rawText: string };

export interface VoiceIntentResult {
  success: boolean;
  message: string;
  navigateTo?: string;
}
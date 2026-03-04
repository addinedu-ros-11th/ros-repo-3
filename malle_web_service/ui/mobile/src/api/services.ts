import { api } from "./client";

// --- Pickup ---
export interface PickupCreateReq {
  pickup_poi_id: number;
  created_channel?: "APP" | "ROBOT";
  items?: { product_id: number; qty: number; unit_price: number }[];
}

export interface PickupOrderRes {
  id: number;
  session_id: number;
  status: string;
  assigned_slot_id: number | null;
  meet_type: string | null;
  meet_poi_id: number | null;
  created_at: string;
}

export const pickupApi = {
  create: (sessionId: number, data: PickupCreateReq) =>
    api.post<PickupOrderRes>(`/sessions/${sessionId}/pickup-orders`, data),

  get: (sessionId: number, orderId: number) =>
    api.get<PickupOrderRes>(`/sessions/${sessionId}/pickup-orders/${orderId}`),

  updateStatus: (sessionId: number, orderId: number, status: string) =>
    api.patch<PickupOrderRes>(`/sessions/${sessionId}/pickup-orders/${orderId}/status`, { status }),

  setMeet: (sessionId: number, orderId: number, data: { meet_type: string; meet_poi_id?: number }) =>
    api.patch<PickupOrderRes>(`/sessions/${sessionId}/pickup-orders/${orderId}/meet`, data),
};

// --- Lockbox ---
export interface LockboxSlotRes {
  id: number;
  robot_id: number;
  slot_no: number;
  status: "EMPTY" | "FULL" | "RESERVED" | "PICKEDUP";
  size_label: string | null;
  // LOCKBOX_UPDATED WS 이벤트에서 활성 주문 정보 포함 (없으면 null)
  order_id?: number | null;
  pickup_poi_id?: number | null;
  store_name?: string | null;
}

export const lockboxApi = {
  getSlots: (robotId: number) => api.get<LockboxSlotRes[]>(`/robots/${robotId}/lockbox`),

  openSlot: (robotId: number, slotNo: number) =>
    api.post(`/robots/${robotId}/lockbox/${slotNo}/open`),

  updateSlotStatus: (robotId: number, slotNo: number, status: string) =>
    api.patch<LockboxSlotRes>(`/robots/${robotId}/lockbox/${slotNo}/status`, { status }),

  createToken: (robotId: number, sessionId: number, slotId?: number) =>
    api.post<{ token: string; expires_at: string }>(`/robots/${robotId}/lockbox/tokens`, {
      session_id: sessionId,
      slot_id: slotId,
    }),

  verifyToken: (robotId: number, token: string, sessionId: number) =>
    api.post(`/robots/${robotId}/lockbox/verify-token`, { token, session_id: sessionId }),
};

// --- Shopping List ---
export interface ShoppingListRes {
  id: number;
  user_id: number;
  name: string;
  status: string;
}

export interface ShoppingItemRes {
  id: number;
  list_id: number;
  store_id: number;
  product_id: number;
  qty: number;
  unit_price: number;
  status: string;
}

export const shoppingApi = {
  getLists: (userId: number) => api.get<ShoppingListRes[]>(`/users/${userId}/shopping-lists`),

  createList: (userId: number, name: string) =>
    api.post<ShoppingListRes>(`/users/${userId}/shopping-lists`, { name }),

  addItem: (listId: number, data: { store_id: number; product_id: number; qty?: number; unit_price?: number }) =>
    api.post<ShoppingItemRes>(`/shopping-lists/${listId}/items`, data),

  toggleItem: (listId: number, itemId: number) =>
    api.patch<ShoppingItemRes>(`/shopping-lists/${listId}/items/${itemId}`),

  removeItem: (listId: number, itemId: number) =>
    api.delete(`/shopping-lists/${listId}/items/${itemId}`),
};

// --- Stores & POIs ---
export interface StoreRes {
  id: number;
  poi_id: number;
  category: string | null;
  name: string | null;
  x_m: number | null;
  y_m: number | null;
}

export interface ProductRes {
  id: number;
  store_id: number;
  name: string;
  price: number;
  sku: string | null;
}

export interface PoiRes {
  id: number;
  name: string;
  type: string;
  x_m: number;
  y_m: number;
  wait_x_m: number | null;
  wait_y_m: number | null;
}

export const storeApi = {
  list: () => api.get<StoreRes[]>("/stores"),
  getProducts: (storeId: number) => api.get<ProductRes[]>(`/stores/${storeId}/products`),
};

export const poiApi = {
  list: (type?: string) => api.get<PoiRes[]>(type ? `/pois?type=${type}` : "/pois"),
};

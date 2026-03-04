import { api } from "./client";

// --- Pickup ---
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
  create: (sessionId: number, data: { pickup_poi_id: number; created_channel?: string; items?: { product_id: number; qty: number; unit_price: number }[] }) =>
    api.post<PickupOrderRes>(`/sessions/${sessionId}/pickup-orders`, data),

  get: (sessionId: number, orderId: number) =>
    api.get<PickupOrderRes>(`/sessions/${sessionId}/pickup-orders/${orderId}`),

  updateStatus: (sessionId: number, orderId: number, status: string) =>
    api.patch<PickupOrderRes>(`/sessions/${sessionId}/pickup-orders/${orderId}/status`, { status }),

  verifyStaffPin: (sessionId: number, orderId: number, pin: string) =>
    api.post(`/sessions/${sessionId}/pickup-orders/${orderId}/staff-pin`, { pin }),

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
      session_id: sessionId, slot_id: slotId,
    }),

  verifyToken: (robotId: number, token: string, sessionId: number) =>
    api.post(`/robots/${robotId}/lockbox/verify-token`, { token, session_id: sessionId }),
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

// --- Robot self-report (voice command → API) ---
export const robotApi = {
  getState: (robotId: number) => api.get(`/robots/${robotId}`),
};

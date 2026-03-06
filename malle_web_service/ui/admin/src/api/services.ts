/**
 * Admin Dashboard API calls.
 * 대시보드에서 사용하는 로봇/미션/이벤트/존/텔레옵 API.
 */
import { api } from "./client";

// --- Robots ---
export interface RobotStateRes {
  x_m: number;
  y_m: number;
  theta_rad: number;
  motion_state: string;
  stop_state: string;
  stop_source: string | null;
  nav_state: string;
  target_poi_id: number | null;
  remaining_distance_m: number;
  eta_sec: number;
  speed_mps: number;
  updated_at: string;
}

export interface RobotRes {
  id: number;
  name: string;
  model: string;
  is_online: boolean;
  battery_pct: number;
  current_mode: string;
  last_seen_at: string | null;
  home_poi_id: number | null;
  state: RobotStateRes | null;
}

export const robotApi = {
  list: () => api.get<{ robots: RobotRes[] }>("/robots"),

  get: (robotId: number) => api.get<RobotRes>(`/robots/${robotId}`),

  triggerEStop: (robotId: number, source = "DASHBOARD") =>
    api.post(`/robots/${robotId}/estop`, { source }),

  releaseEStop: (robotId: number) =>
    api.delete(`/robots/${robotId}/estop`),

  sendCommand: (robotId: number, command: string) =>
    api.post(`/robots/${robotId}/command`, { command }),
};

// --- Missions ---
export interface MissionRes {
  id: number;
  session_id: number;
  robot_id: number;
  type: string;
  status: string;
  created_at: string;
  started_at: string | null;
  ended_at: string | null;
  guide_queue?: { id: number; poi_name: string; status: string; seq: number }[];
}

export const missionApi = {
  list: (params?: { status?: string; robot_id?: number }) => {
    const qs = new URLSearchParams();
    if (params?.status) qs.set("status", params.status);
    if (params?.robot_id) qs.set("robot_id", String(params.robot_id));
    const query = qs.toString();
    return api.get<MissionRes[]>(`/missions${query ? `?${query}` : ""}`);
  },

  get: (missionId: number) => api.get<MissionRes>(`/missions/${missionId}`),

  updateStatus: (missionId: number, status: string) =>
    api.patch<MissionRes>(`/missions/${missionId}/status`, { status }),
};

// --- Events ---
export interface EventRes {
  id: number;
  robot_id: number;
  session_id: number | null;
  type: string;
  severity: string;
  payload_json: Record<string, unknown> | null;
  created_at: string;
}

export const eventApi = {
  list: (params?: { severity?: string; robot_id?: number; type?: string; limit?: number }) => {
    const qs = new URLSearchParams();
    if (params?.severity) qs.set("severity", params.severity);
    if (params?.robot_id) qs.set("robot_id", String(params.robot_id));
    if (params?.type) qs.set("type", params.type);
    if (params?.limit) qs.set("limit", String(params.limit));
    const query = qs.toString();
    return api.get<EventRes[]>(`/events${query ? `?${query}` : ""}`);
  },
};

// --- Zones ---
export const zoneApi = {
  list: () => api.get<Array<{
    id: number;
    name: string;
    polygon_wkt: string;
    is_active: boolean;
    zone_kind: string;
    rule_type?: string;
    speed_limit_mps?: number;
  }>>("/zones"),

  create: (data: { name: string; polygon_wkt: string; zone_kind?: string; is_active?: boolean; rule_type?: string; speed_limit_mps?: number }) =>
    api.post("/zones", data),

  update: (zoneId: number, data: { name?: string; polygon_wkt?: string; is_active?: boolean }) =>
    api.patch(`/zones/${zoneId}`, data),

  delete: (zoneId: number) => api.delete(`/zones/${zoneId}`),
};

// --- Teleop ---
export const teleopApi = {
  start: (robotId: number) => api.post(`/robots/${robotId}/teleop/start`),
  stop: (robotId: number) => api.post(`/robots/${robotId}/teleop/stop`),
  sendCmd: (robotId: number, linear_x: number, angular_z: number) =>
    api.post(`/robots/${robotId}/teleop/cmd`, { linear_x, angular_z }),
};

// --- Lockbox ---
export interface LockboxSlotRes {
  slot_no: number;
  status: string;
  order_id?: number | null;
  pickup_poi_id?: number | null;
  store_name?: string | null;
}

export const lockboxApi = {
  getSlots: (robotId: number) => api.get<LockboxSlotRes[]>(`/robots/${robotId}/lockbox`),
};

// --- Sessions (dashboard view) ---
export const sessionApi = {
  listActive: () => api.get<{ sessions: Array<{ id: number; user_id: number; session_type: string; status: string; assigned_robot_id: number | null; created_at: string }> }>("/sessions/active"),
};

// --- POIs & Stores ---
export const poiApi = {
  list: (type?: string) => api.get(`/pois${type ? `?type=${type}` : ""}`),
};

export const storeApi = {
  list: () => api.get(`/stores`),
};

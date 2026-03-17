/**
 * Session API calls.
 * 모바일 앱에서 세션 생성/조회/상태변경/PIN 검증 등에 사용.
 */
import { api } from "./client";

export interface SessionCreateReq {
  user_id: number;
  session_type: "TASK" | "TIME";
  requested_minutes?: number;
}

export interface SessionRes {
  id: number;
  user_id: number;
  session_type: "TASK" | "TIME";
  requested_minutes: number | null;
  status: string;
  assigned_robot_id: number | null;
  match_pin: string | null;
  pin_expires_at: string | null;
  started_at: string | null;
  ended_at: string | null;
  created_at: string;
  follow_tag_code: number | null;
  follow_tag_family: string | null;
}

export const sessionApi = {
  create: (data: SessionCreateReq) => api.post<SessionRes>("/sessions", data),

  get: (sessionId: number) => api.get<SessionRes>(`/sessions/${sessionId}`),

  updateStatus: (sessionId: number, status: string) =>
    api.patch<SessionRes>(`/sessions/${sessionId}/status`, { status }),

  verifyPin: (sessionId: number, pin: string) =>
    api.post<SessionRes>(`/sessions/${sessionId}/verify-pin`, { pin }),

  setFollowTag: (sessionId: number, tag_code: number, tag_family = "tag36h11") =>
    api.patch<SessionRes>(`/sessions/${sessionId}/follow-tag`, { tag_code, tag_family }),

  end: (sessionId: number) => api.post<SessionRes>(`/sessions/${sessionId}/end`),
};

import { api } from "./client";

export interface GuideQueueItemRes {
  id: number;
  session_id: number;
  poi_id: number;
  poi_name: string | null;
  seq: number;
  status: "PENDING" | "ARRIVED" | "DONE" | "SKIPPED";
  is_active: boolean;
  execution_batch_id: number | null;
  created_at: string;
  completed_at: string | null;
}

export const guideApi = {
  getQueue: (sessionId: number) =>
    api.get<GuideQueueItemRes[]>(`/sessions/${sessionId}/guide-queue`),

  addToQueue: (sessionId: number, poi_id: number) =>
    api.post<GuideQueueItemRes>(`/sessions/${sessionId}/guide-queue`, { poi_id }),

  removeFromQueue: (sessionId: number, itemId: number) =>
    api.delete(`/sessions/${sessionId}/guide-queue/${itemId}`),

  updateItemStatus: (sessionId: number, itemId: number, status: string) =>
    api.patch<GuideQueueItemRes>(`/sessions/${sessionId}/guide-queue/${itemId}`, { status }),

  execute: (sessionId: number) =>
    api.post<{ ok: boolean; mission_id: number; executing_count: number }>(
      `/sessions/${sessionId}/guide-queue/execute`
    ),

  clear: (sessionId: number) =>
    api.delete(`/sessions/${sessionId}/guide-queue`),

  advance: (sessionId: number) =>
    api.post(`/sessions/${sessionId}/guide-queue/advance`),
};

/**
 * Robot WebSocket event handler.
 * useWebSocket 훅으로 받은 메시지를 robotStore 액션으로 라우팅.
 *
 * 사용법 (App.tsx):
 *   const robotId = useRobotStore(s => s.robot.id);
 *   useWsHandler(robotId);
 */
import { useEffect } from "react";
import { useWebSocket, type WsMessage } from "./useWebSocket";
import { useRobotStore } from "@/stores/robotStore";
import { sessionApi } from "@/api/sessions";
import type { GuideQueueItem, GuideQueueStatus, FollowStatus, PickupStatus } from "@/types/robot";

export function useWsHandler(robotId: string | null) {
  const store = useRobotStore();

  const { send } = useWebSocket({
    path: robotId ? `/ws/robot/${robotId}` : "",
    onMessage: (msg: WsMessage) => handleWsMessage(msg, store),
    reconnect: !!robotId,
  });

  useEffect(() => {
    if (!robotId) return;
    const interval = setInterval(() => send("PING"), 30000);
    return () => clearInterval(interval);
  }, [robotId, send]);

  return { send };
}

/* ───── payload → store 매핑 ───── */

function handleWsMessage(msg: WsMessage, store: ReturnType<typeof useRobotStore.getState>) {
  const { type, payload } = msg;
  const p = payload as Record<string, any>;

  switch (type) {
    /* ───── Session events ───── */

    case "SESSION_ASSIGNED": {
      // payload: SessionAssignedPayload { id, match_pin, robot_name, battery_pct, customer_phone_masked, eta_sec, ... }
      const sessionId = p.id as number;
      useRobotStore.setState({
        currentSessionId: sessionId ?? null,
        sessionState: "APPROACHING",
      });
      store.addNotification({
        category: "SYSTEM",
        title: "New Session Assigned",
        description: `Customer ${p.customer_phone_masked || "Unknown"} — approaching`,
      });

      // 데모: 세션 배정 후 MATCHING으로 전환
      // 2초 딜레이 — 모바일이 WS /ws/mobile/{session_id} 연결할 시간 확보
      // 실제 배포에서는 Nav2 도착 콜백(bridge_node)에서 호출
      if (sessionId) {
        setTimeout(() => {
          sessionApi.updateStatus(sessionId, "MATCHING").catch((e) => {
            console.error("[WS] Failed to transition to MATCHING:", e);
          });
        }, 2000);
      }
      break;
    }

    case "PIN_MATCHING": {
      // 서버가 MATCHING 상태로 전환됐을 때 수신
      // payload: { session_id, pin }
      useRobotStore.setState({
        sessionState: "PIN_MATCHING",
        showPinOverlay: true,
      });
      break;
    }

    case "SESSION_ACTIVE": {
      // payload: { id, session_type, remaining_time, customer_name, ... }
      const sessionType = p.session_type || "TIME";
      const remaining = p.remaining_time ?? (p.requested_minutes ? p.requested_minutes * 60 : 7200);
      const customerName = p.customer_name || "Customer";
      store.startSession(sessionType, remaining, customerName);
      useRobotStore.setState({ currentSessionId: p.id ?? useRobotStore.getState().currentSessionId });
      break;
    }

    case "SESSION_ENDED":
      store.endSession();
      store.addNotification({
        category: "SYSTEM",
        title: "Session Ended",
        description: "Customer session has ended",
      });
      break;

    /* ───── Guide events ───── */

    case "GUIDE_QUEUE_UPDATED": {
      // payload: { queue: GuideQueueItemRes[] }
      const queue: GuideQueueItem[] = (p.queue || []).map((item: any) => ({
        id: String(item.id),             // 서버 item id를 UI id로도 사용 (일관성)
        serverItemId: item.id as number, // DELETE/PATCH용 숫자 id
        poiId: String(item.poi_id),
        poiName: item.poi_name || `POI #${item.poi_id}`,
        floor: "Level 1",
        estimatedTime: item.estimated_time ?? 3,
        status: mapGuideStatus(item.status, item.is_active),
        selected: true,
      }));
      store._setGuideQueueFromServer(queue);
      break;
    }

    case "GUIDE_NAVIGATING": {
      // payload: { item_id, poi_id, poi_name }
      const itemId = String(p.item_id);
      store.setGuideItemStatus(itemId, "IN_PROGRESS");
      if (!useRobotStore.getState().guide.isExecuting) {
        useRobotStore.setState((s) => ({
          activeMode: "GUIDE",
          guide: { ...s.guide, isExecuting: true },
          robot: { ...s.robot, status: "MOVING" },
        }));
      }
      store.addNotification({
        category: "NAVIGATION",
        title: `Navigating to ${p.poi_name || "destination"}`,
        description: "Guide navigation started",
      });
      break;
    }

    case "GUIDE_ARRIVED": {
      // payload: { item_id, poi_name }
      const itemId = String(p.item_id);
      store.setGuideItemStatus(itemId, "ARRIVED");
      useRobotStore.setState((s) => ({
        robot: { ...s.robot, status: "WAITING" },
      }));
      store.addNotification({
        category: "NAVIGATION",
        title: `Arrived at ${p.poi_name || "destination"}`,
        description: "Waiting for customer",
      });
      break;
    }

    /* ───── Follow events ───── */

    case "FOLLOW_STARTED": {
      const tagCode = p.tag_code ?? p.tagId ?? 11;
      if (!useRobotStore.getState().follow.active) {
        store.startFollow(tagCode as 11 | 12 | 13);
      }
      break;
    }

    case "FOLLOW_STOPPED":
      store.stopFollow();
      break;

    case "FOLLOW_STATUS":
      if (p.status) store.setFollowStatus(p.status as FollowStatus);
      break;

    /* ───── Pickup events ───── */

    case "PICKUP_STATUS_CHANGED": {
      // payload: { status, order_id, ... }
      const status = p.status as PickupStatus;
      if (status) {
        store.setPickupStatus(status);
        if (status === "LOADED") store.setShowLoadingOverlay(true);
        if (status === "DONE") store.completePickup();
      }
      store.addNotification({
        category: "PICKUP",
        title: "Pickup Status Update",
        description: `Order status: ${p.status}`,
      });
      break;
    }

    case "PICKUP_MEET_SET":
      // payload: { meet_poi_name, meet_type }
      if (p.meet_poi_name && useRobotStore.getState().pickup.currentOrder) {
        useRobotStore.setState((s) => ({
          pickup: s.pickup.currentOrder
            ? { ...s.pickup, currentOrder: { ...s.pickup.currentOrder, meetupLocation: p.meet_poi_name } }
            : s.pickup,
        }));
      }
      break;

    /* ───── Lockbox events ───── */

    case "LOCKBOX_OPENED":
      if (p.slot_no) {
        store.openSlot(p.slot_no);
        store.addNotification({
          category: "LOCKBOX",
          title: `Slot ${p.slot_no} Opened`,
          description: "Lockbox slot opened remotely",
        });
      }
      break;

    case "LOCKBOX_UPDATED": {
      // payload: { slots: [{ slot_no, status, size_label }] }
      const updatedSlots = (p.slots as any[]) ?? [];
      if (updatedSlots.length) {
        const mapped = updatedSlots.map((s: any) => ({
          number: s.slot_no as number,
          status: (s.status === "FULL" ? "FULL"
                 : s.status === "RESERVED" ? "RESERVED"
                 : s.status === "PICKEDUP" ? "FULL"
                 : "EMPTY") as "EMPTY" | "FULL" | "RESERVED",
          size: s.size_label ?? undefined,
        }));
        useRobotStore.setState({ lockboxSlots: mapped });
      }
      break;
    }

    case "LOCKBOX_STORED":
      if (p.slot_no) {
        store.setSlotStatus(p.slot_no, "FULL");
        store.addLockboxLog({
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          slotNumber: p.slot_no,
          action: "SECURED",
          result: "SUCCESS",
          description: `Slot ${p.slot_no} secured`,
        });
      }
      break;

    /* ───── Robot state ───── */

    case "ROBOT_STATE_UPDATED": {
      // payload: { battery_pct, nav_state, command, x_m, y_m, ... }
      if (p.battery_pct !== undefined) store.setBattery(p.battery_pct);
      if (p.command === "return_station") {
        store.addNotification({
          category: "SYSTEM",
          title: "Return to Station",
          description: "Robot is returning to charging station",
        });
      }
      break;
    }

    case "ROBOT_ESTOP":
      store.setRobotStatus("STOPPED");
      store.addNotification({
        category: "SYSTEM",
        title: "🛑 Emergency Stop",
        description: "Robot has been emergency stopped",
      });
      break;

    case "ROBOT_ESTOP_RELEASED":
      store.setRobotStatus("IDLE");
      store.addNotification({
        category: "SYSTEM",
        title: "E-Stop Released",
        description: "Robot is ready to operate",
      });
      break;

    case "PONG":
      break;

    default:
      console.log("[WS] Unhandled event:", type, payload);
  }
}

/* 서버 status → 프론트 GuideQueueStatus 변환 */
function mapGuideStatus(status: string, _isActive?: boolean): GuideQueueStatus {
  switch (status) {
    case "ARRIVED": return "ARRIVED";
    case "DONE": return "DONE";
    case "SKIPPED": return "DONE";
    case "PENDING": return "PENDING";
    default: return "PENDING";
  }
}
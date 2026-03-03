/**
 * Mobile WebSocket event handler.
 * useWebSocket 훅으로 받은 메시지를 appStore 액션으로 라우팅.
 *
 * 사용법 (App.tsx):
 *   const sessionId = useAppStore(s => s.currentSessionId);
 *   useWsHandler(sessionId);
 */
import { useEffect } from "react";
import { useWebSocket, type WsMessage } from "./useWebSocket";
import { useAppStore, type GuideDestination, type GuideStatus, type PickupStatus, type FollowStatus } from "@/store/appStore";

export function useWsHandler(sessionId: number | null) {
  const store = useAppStore();

  const { send } = useWebSocket({
    path: sessionId ? `/ws/mobile/${sessionId}` : "",
    onMessage: (msg: WsMessage) => handleWsMessage(msg, store),
    reconnect: !!sessionId,
  });

  // Ping every 30s to keep alive
  useEffect(() => {
    if (!sessionId) return;
    const interval = setInterval(() => send("PING"), 30000);
    return () => clearInterval(interval);
  }, [sessionId, send]);

  return { send };
}

/* ───── payload → store 매핑 ───── */

function handleWsMessage(msg: WsMessage, store: ReturnType<typeof useAppStore.getState>) {
  const { type, payload } = msg;
  const p = payload as Record<string, any>;

  switch (type) {
    /* ───── Session events ───── */

    case "SESSION_ASSIGNED": {
      // payload: { id, assigned_robot_id, match_pin, ... }
      const robotId = p.assigned_robot_id;
      if (robotId) {
        useAppStore.setState({
          currentRobotId: robotId,
          matchPin: p.match_pin ?? null,
        });
        store.assignRobot({
          id: String(robotId),
          name: p.robot_name || `Mall·E-${robotId}`,
          battery: p.battery_pct ?? 80,
          mode: null,
          location: { x: p.x_m ?? 0, y: p.y_m ?? 0 },
        });
        store.initLockboxSlots(robotId);
      }
      break;
    }

    case "ROBOT_APPROACHING":
      // payload: { id, status, eta_sec }
      useAppStore.setState({ sessionState: "APPROACHING" });
      if (p.eta_sec) useAppStore.setState({ approachingEta: p.eta_sec });
      break;

    case "PIN_MATCHING":
      // payload: { session_id, pin }
      if (p.pin) useAppStore.setState({ matchPin: p.pin });
      store.startPinMatching();
      break;

    case "SESSION_ACTIVE":
      store.activateSession();
      break;

    case "SESSION_ENDED":
      // API 재호출 방지 — 상태만 초기화
      store._resetOnSessionEnded();
      break;

    /* ───── Guide events ───── */

    case "GUIDE_QUEUE_UPDATED": {
      // payload: { queue: GuideQueueItemRes[] }
      const queue: GuideDestination[] = (p.queue || []).map((item: any) => ({
        id: String(item.id),           // 서버 item id를 UI id로도 사용 (일관성)
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

    case "GUIDE_NAVIGATING":
      // payload: { item_id, poi_name }
      useAppStore.setState((s) => ({
        guideQueue: s.guideQueue.map((i) =>
          i.id === String(p.item_id) ? { ...i, status: "IN_PROGRESS" as GuideStatus } : i
        ),
      }));
      break;

    case "GUIDE_ARRIVED":
      // payload: { item_id, poi_name }
      useAppStore.setState((s) => ({
        guideQueue: s.guideQueue.map((i) =>
          i.id === String(p.item_id) ? { ...i, status: "ARRIVED" as GuideStatus } : i
        ),
      }));
      break;

    /* ───── Follow events ───── */

    case "FOLLOW_STARTED":
      if (!useAppStore.getState().followMe.active) {
        store.startFollowMe(p.tag_code ?? 11);
      }
      break;

    case "FOLLOW_STOPPED":
      store.stopFollowMe();
      break;

    case "FOLLOW_STATUS":
      // payload: { status: "FOLLOWING" | "LOST" | "RECONNECTING" }
      if (p.status) store.setFollowStatus(p.status as FollowStatus);
      break;

    /* ───── Pickup events ───── */

    case "PICKUP_STATUS_CHANGED": {
      const mappedStatus = mapPickupStatus(p.status as string) as PickupStatus;
      const currentOrder = useAppStore.getState().pickupOrder;
      const serverOrderId = p.id as number;

      // 현재 주문이 있고 같은 주문이면 상태 업데이트
      if (currentOrder && (currentOrder.serverOrderId === serverOrderId || currentOrder.serverOrderId === null)) {
        if (mappedStatus === 'DONE') {
          // COMPLETED → pickupOrder null로 초기화해서 다음 주문 받을 수 있게
          useAppStore.setState({ pickupOrder: null });
        } else {
          store.setPickupStatus(mappedStatus);
        }
      } else if (!currentOrder && mappedStatus !== 'DONE') {
        // Robot이 생성한 새 주문 수신
        const appStores = useAppStore.getState().stores;
        const storeMatch = appStores.find((s) => s.poi_id === (p.pickup_poi_id as number));
        const storeName = storeMatch?.name ?? `Pickup #${p.id}`;
        useAppStore.setState({
          pickupOrder: {
            orderId: `#${p.id}`,
            serverOrderId: p.id as number,
            storeId: String(p.pickup_poi_id ?? ''),
            storeName,
            items: [],
            status: mappedStatus,
            meetupLocation: null,
            slotId: (p.assigned_slot_id as number | null) ?? null,
          },
        });
      }
      break;
    }

    case "PICKUP_MEET_SET":
      // payload: { meet_poi_name, meet_type }
      if (p.meet_poi_name) store.setMeetupLocation(p.meet_poi_name);
      break;

    /* ───── Lockbox events ───── */

    case "LOCKBOX_OPENED":
      // API 재호출 없이 로그만 기록 (openSlot()을 호출하면 API 무한루프 발생)
      if (p.slot_no) store._onLockboxOpened(p.slot_no);
      break;

    case "LOCKBOX_UPDATED": {
      // payload: { slots: SlotResponse[] }
      console.log("[WS] LOCKBOX_UPDATED received", p.slots);
      const slots = (p.slots as any[]) ?? [];
      if (slots.length) store._setLockboxSlotsFromServer(slots);
      break;
    }

    case "LOCKBOX_STORED":
      // 상태는 LOCKBOX_UPDATED로 처리; 여기선 로그만 추가
      if (p.slot_no) {
        useAppStore.setState((s) => ({
          lockboxLogs: [
            { id: `log-${Date.now()}`, timestamp: new Date(), slotNumber: p.slot_no, action: "SECURED" as const, result: "SUCCESS" as const, description: `Slot ${p.slot_no} secured` },
            ...s.lockboxLogs,
          ].slice(0, 10),
        }));
      }
      break;

    /* ───── Robot events ───── */

    case "ROBOT_STATE_UPDATED":
      // payload: { battery_pct, x_m, y_m, ... }
      store._updateRobotState({
        battery_pct: p.battery_pct,
        x_m: p.x_m,
        y_m: p.y_m,
      });
      break;

    case "ROBOT_ESTOP":
      useAppStore.setState((s) => ({
        robot: s.robot ? { ...s.robot, mode: null } : null,
        followMe: s.followMe.active ? { ...s.followMe, status: "STOPPED" as FollowStatus } : s.followMe,
      }));
      console.warn("[WS] ROBOT E-STOP activated");
      break;

    case "ROBOT_ESTOP_RELEASED":
      console.log("[WS] ROBOT E-STOP released");
      break;

    case "PONG":
      break;

    default:
      console.log("[WS] Unhandled event:", type, payload);
  }
}

/* 서버 PickupStatus → 프론트 PickupStatus 변환 */
function mapPickupStatus(serverStatus: string): string {
  switch (serverStatus) {
    case "CREATED":   return "MOVING";
    case "LOADED":    return "LOADED";
    case "MEET_SET":  return "MEETUP_SET";
    case "COMPLETED": return "DONE";
    default:          return serverStatus;
  }
}

/* 서버 status → 프론트 GuideStatus 변환 */
function mapGuideStatus(status: string, _isActive?: boolean): GuideStatus {
  switch (status) {
    case "ARRIVED": return "ARRIVED";
    case "DONE": return "DONE";
    case "SKIPPED": return "DONE";
    case "PENDING": return "PENDING";
    default: return "PENDING";
  }
}
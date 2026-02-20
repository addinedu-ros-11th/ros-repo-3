// /**
//  * Robot WebSocket event handler.
//  * useWebSocket 훅으로 받은 메시지를 robotStore 액션으로 라우팅.
//  *
//  * 사용법 (App.tsx):
//  *   const robotId = useRobotStore(s => s.robot.id);
//  *   useWsHandler(robotId);
//  */
// import { useEffect } from "react";
// import { useWebSocket, type WsMessage } from "./useWebSocket";
// import { useRobotStore } from "@/stores/robotStore";
// import type { GuideQueueItem, GuideQueueStatus, FollowStatus, PickupStatus } from "@/types/robot";

// export function useWsHandler(robotId: string | null) {
//   const store = useRobotStore();

//   const { send } = useWebSocket({
//     path: robotId ? `/ws/robot/${robotId}` : "",
//     onMessage: (msg: WsMessage) => handleWsMessage(msg, store),
//     reconnect: !!robotId,
//   });

//   useEffect(() => {
//     if (!robotId) return;
//     const interval = setInterval(() => send("PING"), 30000);
//     return () => clearInterval(interval);
//   }, [robotId, send]);

//   return { send };
// }

// /* ───── payload → store 매핑 ───── */

// function handleWsMessage(msg: WsMessage, store: ReturnType<typeof useRobotStore.getState>) {
//   const { type, payload } = msg;
//   const p = payload as Record<string, any>;

//   switch (type) {
//     /* ───── Session events ───── */

//     case "SESSION_ASSIGNED": {
//       // payload: { id, user_id, session_type, match_pin, assigned_robot_id, customer_name, ... }
//       useRobotStore.setState({
//         currentSessionId: p.id ?? null,
//         sessionState: "PIN_MATCHING",
//         showPinOverlay: true,
//       });
//       store.addNotification({
//         category: "SYSTEM",
//         title: "New Session Assigned",
//         description: `Customer ${p.customer_name || "Unknown"} — PIN matching required`,
//       });
//       break;
//     }

//     case "SESSION_ACTIVE": {
//       // payload: { id, session_type, remaining_time, customer_name, ... }
//       const sessionType = p.session_type || "TIME";
//       const remaining = p.remaining_time ?? p.requested_minutes ? (p.requested_minutes * 60) : 7200;
//       const customerName = p.customer_name || "Customer";
//       store.startSession(sessionType, remaining, customerName);
//       useRobotStore.setState({ currentSessionId: p.id ?? useRobotStore.getState().currentSessionId });
//       break;
//     }

//     case "SESSION_ENDED":
//       store.endSession();
//       store.addNotification({
//         category: "SYSTEM",
//         title: "Session Ended",
//         description: "Customer session has ended",
//       });
//       break;

//     /* ───── Guide events ───── */

//     case "GUIDE_QUEUE_UPDATED": {
//       // payload: { queue: GuideQueueItemRes[] }
//       const queue: GuideQueueItem[] = (p.queue || []).map((item: any) => ({
//         id: String(item.id),
//         poiName: item.poi_name || `POI #${item.poi_id}`,
//         floor: "Level 1",
//         estimatedTime: item.estimated_time ?? 3,
//         status: mapGuideStatus(item.status, item.is_active),
//         selected: true,
//       }));
//       store._setGuideQueueFromServer(queue);
//       break;
//     }

//     case "GUIDE_NAVIGATING": {
//       // payload: { item_id, poi_id, poi_name }
//       const itemId = String(p.item_id);
//       store.setGuideItemStatus(itemId, "IN_PROGRESS");
//       // 가이드가 실행 중이 아니면 시작
//       if (!useRobotStore.getState().guide.isExecuting) {
//         useRobotStore.setState((s) => ({
//           activeMode: "GUIDE",
//           guide: { ...s.guide, isExecuting: true },
//           robot: { ...s.robot, status: "MOVING" },
//         }));
//       }
//       store.addNotification({
//         category: "NAVIGATION",
//         title: `Navigating to ${p.poi_name || "destination"}`,
//         description: "Guide navigation started",
//       });
//       break;
//     }

//     case "GUIDE_ARRIVED": {
//       // payload: { item_id, poi_name }
//       const itemId = String(p.item_id);
//       store.setGuideItemStatus(itemId, "ARRIVED");
//       useRobotStore.setState((s) => ({
//         robot: { ...s.robot, status: "WAITING" },
//       }));
//       store.addNotification({
//         category: "NAVIGATION",
//         title: `Arrived at ${p.poi_name || "destination"}`,
//         description: "Waiting for customer",
//       });
//       break;
//     }

//     /* ───── Follow events ───── */

//     case "FOLLOW_STARTED": {
//       const tagCode = p.tag_code ?? p.tagId ?? 11;
//       if (!useRobotStore.getState().follow.active) {
//         store.startFollow(tagCode as 11 | 12 | 13);
//       }
//       break;
//     }

//     case "FOLLOW_STOPPED":
//       store.stopFollow();
//       break;

//     case "FOLLOW_STATUS":
//       if (p.status) store.setFollowStatus(p.status as FollowStatus);
//       break;

//     /* ───── Pickup events ───── */

//     case "PICKUP_STATUS_CHANGED": {
//       // payload: { status, order_id, ... }
//       const status = p.status as PickupStatus;
//       if (status) {
//         store.setPickupStatus(status);
//         // LOADED → 로딩 오버레이 표시
//         if (status === "LOADED") store.setShowLoadingOverlay(true);
//         // DONE → 완료 처리
//         if (status === "DONE") store.completePickup();
//       }
//       store.addNotification({
//         category: "PICKUP",
//         title: "Pickup Status Update",
//         description: `Order status: ${p.status}`,
//       });
//       break;
//     }

//     case "PICKUP_MEET_SET":
//       // payload: { meet_poi_name, meet_type }
//       if (p.meet_poi_name && useRobotStore.getState().pickup.currentOrder) {
//         useRobotStore.setState((s) => ({
//           pickup: s.pickup.currentOrder
//             ? { ...s.pickup, currentOrder: { ...s.pickup.currentOrder, meetupLocation: p.meet_poi_name } }
//             : s.pickup,
//         }));
//       }
//       break;

//     /* ───── Lockbox events ───── */

//     case "LOCKBOX_OPENED":
//       if (p.slot_no) {
//         store.openSlot(p.slot_no);
//         store.addNotification({
//           category: "LOCKBOX",
//           title: `Slot ${p.slot_no} Opened`,
//           description: "Lockbox slot opened remotely",
//         });
//       }
//       break;

//     case "LOCKBOX_STORED":
//       if (p.slot_no) {
//         store.setSlotStatus(p.slot_no, "FULL");
//         store.addLockboxLog({
//           timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
//           slotNumber: p.slot_no,
//           action: "SECURED",
//           result: "SUCCESS",
//           description: `Slot ${p.slot_no} secured`,
//         });
//       }
//       break;

//     /* ───── Robot state ───── */

//     case "ROBOT_STATE_UPDATED": {
//       // payload: { battery_pct, nav_state, command, x_m, y_m, ... }
//       if (p.battery_pct !== undefined) store.setBattery(p.battery_pct);
//       if (p.command === "return_station") {
//         store.addNotification({
//           category: "SYSTEM",
//           title: "Return to Station",
//           description: "Robot is returning to charging station",
//         });
//       }
//       break;
//     }

//     case "ROBOT_ESTOP":
//       store.setRobotStatus("STOPPED");
//       store.addNotification({
//         category: "SYSTEM",
//         title: "🛑 Emergency Stop",
//         description: "Robot has been emergency stopped",
//       });
//       break;

//     case "ROBOT_ESTOP_RELEASED":
//       store.setRobotStatus("IDLE");
//       store.addNotification({
//         category: "SYSTEM",
//         title: "E-Stop Released",
//         description: "Robot is ready to operate",
//       });
//       break;

//     case "PONG":
//       break;

//     default:
//       console.log("[WS] Unhandled event:", type, payload);
//   }
// }

// /* 서버 status → 프론트 GuideQueueStatus 변환 */
// function mapGuideStatus(status: string, isActive?: boolean): GuideQueueStatus {
//   switch (status) {
//     case "ARRIVED": return "ARRIVED";
//     case "DONE": return "DONE";
//     case "SKIPPED": return "DONE";
//     default: return isActive ? "IN_PROGRESS" : "PENDING";
//   }
// }

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
      // payload: { id, user_id, session_type, match_pin, assigned_robot_id, customer_name, ... }
      useRobotStore.setState({
        currentSessionId: p.id ?? null,
        sessionState: "PIN_MATCHING",
        showPinOverlay: true,
      });
      store.addNotification({
        category: "SYSTEM",
        title: "New Session Assigned",
        description: `Customer ${p.customer_name || "Unknown"} — PIN matching required`,
      });
      break;
    }

    case "SESSION_ACTIVE": {
      // payload: { id, session_type, remaining_time, customer_name, ... }
      const sessionType = p.session_type || "TIME";
      const remaining = p.remaining_time ?? p.requested_minutes ? (p.requested_minutes * 60) : 7200;
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
        id: String(item.id),
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
      // 가이드가 실행 중이 아니면 시작
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
        // LOADED → 로딩 오버레이 표시
        if (status === "LOADED") store.setShowLoadingOverlay(true);
        // DONE → 완료 처리
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
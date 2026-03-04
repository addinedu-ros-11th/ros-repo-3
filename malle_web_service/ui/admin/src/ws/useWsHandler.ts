/**
 * Dashboard WebSocket event handler.
 * /ws/dashboard에 연결하여 모든 로봇/미션/이벤트 브로드캐스트 수신.
 *
 * DashboardProvider 내부에서 사용:
 *   useWsHandler({ onRobotStateUpdated, onEStop, ... });
 */
import { useEffect } from "react";
import { useWebSocket, type WsMessage } from "./useWebSocket";

interface DashboardWsCallbacks {
  onRobotStateUpdated: (robotId: number, state: Record<string, unknown>) => void;
  onEStop: (robotId: number, source: string) => void;
  onEStopReleased: (robotId: number) => void;
  onMissionCreated: (data: Record<string, unknown>) => void;
  onMissionUpdated: (data: Record<string, unknown>) => void;
  onSessionAssigned: (data: Record<string, unknown>) => void;
  onEventReceived: (data: Record<string, unknown>) => void;
  onGuideArrived: (data: Record<string, unknown>) => void;
  onPickupStatusChanged: (data: Record<string, unknown>) => void;
  onLockboxOpened: (data: Record<string, unknown>) => void;
  onLockboxUpdated: (robotId: number, slots: Record<string, any>[]) => void;
  onFollowStarted: (data: Record<string, unknown>) => void;
  onFollowStopped: (data: Record<string, unknown>) => void;
}

export function useWsHandler(callbacks: DashboardWsCallbacks) {
  const { send } = useWebSocket({
    path: "/ws/dashboard",
    onMessage: (msg: WsMessage) => handleWsMessage(msg, callbacks),
    reconnect: true,
  });

  useEffect(() => {
    const interval = setInterval(() => send("PING"), 30000);
    return () => clearInterval(interval);
  }, [send]);

  return { send };
}

function handleWsMessage(msg: WsMessage, cb: DashboardWsCallbacks) {
  const { type, payload } = msg;
  const p = payload as Record<string, any>;

  switch (type) {
    /* ───── Robot state ───── */

    case "ROBOT_STATE_UPDATED":
      if (p.robot_id != null) cb.onRobotStateUpdated(p.robot_id, p);
      break;

    case "ROBOT_ESTOP":
      if (p.robot_id != null) cb.onEStop(p.robot_id, p.source || "ROBOT");
      break;

    case "ROBOT_ESTOP_RELEASED":
      if (p.robot_id != null) cb.onEStopReleased(p.robot_id);
      break;

    case "ROBOT_EVENT":
      cb.onEventReceived(p);
      break;

    /* ───── Mission ───── */

    case "MISSION_CREATED":
      cb.onMissionCreated(p);
      break;

    case "MISSION_UPDATED":
      cb.onMissionUpdated(p);
      break;

    /* ───── Session ───── */

    case "SESSION_ASSIGNED":
      cb.onSessionAssigned(p);
      break;

    case "ROBOT_APPROACHING":
      cb.onEventReceived({
        type: "ROBOT_APPROACHING",
        severity: "INFO",
        robot_id: p.robot_id,
        session_id: p.session_id,
        message: `Robot R-${p.robot_id} approaching for session S-${p.session_id}`,
        created_at: new Date().toISOString(),
      });
      break;

    case "SESSION_ACTIVE":
      cb.onEventReceived({
        type: "SESSION_ACTIVE",
        severity: "INFO",
        robot_id: p.assigned_robot_id,
        session_id: p.id,
        message: `Session S-${p.id} is now active`,
        created_at: new Date().toISOString(),
      });
      break;

    case "SESSION_ENDED":
      // 세션 종료 → 이벤트로 기록
      cb.onEventReceived({
        type: "MISSION_COMPLETE",
        severity: "INFO",
        robot_id: p.robot_id ?? p.assigned_robot_id,
        session_id: p.id,
        message: `Session S-${p.id} ended`,
        created_at: new Date().toISOString(),
      });
      break;

    /* ───── Guide ───── */

    case "GUIDE_ARRIVED":
      cb.onGuideArrived(p);
      break;

    case "GUIDE_NAVIGATING":
      // 네비게이션 시작 → 이벤트 기록
      cb.onEventReceived({
        type: "MISSION_COMPLETE",
        severity: "INFO",
        robot_id: p.robot_id,
        session_id: p.session_id,
        message: `Navigating to ${p.poi_name || "destination"}`,
        created_at: new Date().toISOString(),
      });
      break;

    /* ───── Follow ───── */

    case "FOLLOW_STARTED":
      cb.onFollowStarted(p);
      break;

    case "FOLLOW_STOPPED":
      cb.onFollowStopped(p);
      break;

    /* ───── Pickup ───── */

    case "PICKUP_STATUS_CHANGED":
      cb.onPickupStatusChanged(p);
      break;

    case "PICKUP_MEET_SET":
      cb.onEventReceived({
        type: "PICKUP_MEET_SET",
        severity: "INFO",
        robot_id: p.robot_id,
        session_id: p.session_id,
        message: `Pickup meet point set for session S-${p.session_id}`,
        created_at: new Date().toISOString(),
      });
      break;

    /* ───── Lockbox ───── */

    case "LOCKBOX_OPENED":
      cb.onLockboxOpened(p);
      break;

    case "LOCKBOX_STORED":
      cb.onEventReceived({
        type: "LOCKBOX_STORED",
        severity: "INFO",
        robot_id: p.robot_id,
        session_id: p.session_id,
        message: `Lockbox slot ${p.slot ?? ""} stored`,
        created_at: new Date().toISOString(),
      });
      break;

    case "LOCKBOX_UPDATED":
      if (p.robot_id != null) cb.onLockboxUpdated(p.robot_id, (p.slots as any[]) ?? []);
      break;

    case "PONG":
      break;

    default:
      console.log("[WS] Unhandled dashboard event:", type, payload);
  }
}
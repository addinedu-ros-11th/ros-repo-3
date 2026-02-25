import { useEffect } from "react";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { RobotLayout } from "@/components/layout/RobotLayout";
import { HomePage } from "@/pages/HomePage";
import { ModePage } from "@/pages/ModePage";
import { GuidePage } from "@/pages/GuidePage";
import { FollowPage } from "@/pages/FollowPage";
import { PickupPage } from "@/pages/PickupPage";
import { MapPage } from "@/pages/MapPage";
import { LockboxPage } from "@/pages/LockboxPage";
import { SearchPage } from "@/pages/SearchPage";
import NotFound from "./pages/NotFound";
import { useRobotStore } from "@/stores/robotStore";
import { useWsHandler } from "@/ws/useWsHandler";

const queryClient = new QueryClient();

// Robot ID comes from VITE_ROBOT_ID env var (set per-device in .env.local).
// Falls back to '1' for dev convenience.
const ROBOT_ID = import.meta.env.VITE_ROBOT_ID ?? "1";

/** WS 연결 + 서버에서 로봇 초기 상태 fetch */
function RobotInit() {
  const robotId = useRobotStore((s) => s.robot.id);

  useEffect(() => {
    // 앱 시작 시 store에 실제 robot ID 세팅 (env에서 읽은 값)
    if (robotId !== ROBOT_ID) {
      useRobotStore.setState((s) => ({
        robot: { ...s.robot, id: ROBOT_ID, name: `Mall·E-${ROBOT_ID}` },
        currentRobotId: Number(ROBOT_ID),
      }));
    }
  }, []);

  // 로봇은 항상 WS 연결 (robotId는 고정)
  useWsHandler(robotId);

  return null;
}

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <RobotInit />
        <Routes>
          <Route element={<RobotLayout />}>
            <Route path="/" element={<HomePage />} />
            <Route path="/mode" element={<ModePage />} />
            <Route path="/mode/guide" element={<GuidePage />} />
            <Route path="/mode/follow" element={<FollowPage />} />
            <Route path="/mode/pickup" element={<PickupPage />} />
            <Route path="/map" element={<MapPage />} />
            <Route path="/lockbox" element={<LockboxPage />} />
            <Route path="/search" element={<SearchPage />} />
          </Route>
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
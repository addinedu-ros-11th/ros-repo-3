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

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
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

import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { DashboardProvider } from "@/context/DashboardContext";
import DashboardLayout from "@/components/DashboardLayout";
import Overview from "./pages/Overview";
import FleetMap from "./pages/FleetMap";
import ManualControl from "./pages/ManualControl";
import Zones from "./pages/Zones";
import Missions from "./pages/Missions";
import Analytics from "./pages/Analytics";
import Events from "./pages/Events";
import CameraPage from "./pages/CameraPage";
import NotFound from "./pages/NotFound";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <DashboardProvider>
        <Toaster />
        <Sonner />
        <BrowserRouter>
          <Routes>
            <Route element={<DashboardLayout />}>
              <Route path="/" element={<Overview />} />
              <Route path="/fleet-map" element={<FleetMap />} />
              <Route path="/manual-control" element={<ManualControl />} />
              <Route path="/zones" element={<Zones />} />
              <Route path="/missions" element={<Missions />} />
              <Route path="/analytics" element={<Analytics />} />
              <Route path="/events" element={<Events />} />
              <Route path="/camera" element={<CameraPage />} />
            </Route>
            <Route path="*" element={<NotFound />} />
          </Routes>
        </BrowserRouter>
      </DashboardProvider>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;

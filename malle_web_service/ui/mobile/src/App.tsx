import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AppLayout } from "./components/layout/AppLayout";
import Home from "./pages/Home";
import Mode from "./pages/Mode";
import GuideMode from "./pages/GuideMode";
import GuideActive from "./pages/GuideActive";
import FollowMode from "./pages/FollowMode";
import PickupMode from "./pages/PickupMode";
import MapPage from "./pages/MapPage";
import Lockbox from "./pages/Lockbox";
import ShoppingList from "./pages/ShoppingList";
import TaskComplete from "./pages/TaskComplete";
import NotFound from "./pages/NotFound";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<AppLayout><Home /></AppLayout>} />
          <Route path="/mode" element={<AppLayout><Mode /></AppLayout>} />
          <Route path="/mode/guide" element={<AppLayout><GuideMode /></AppLayout>} />
          <Route path="/mode/guide/active" element={<AppLayout><GuideActive /></AppLayout>} />
          <Route path="/mode/follow" element={<AppLayout><FollowMode /></AppLayout>} />
          <Route path="/mode/pickup" element={<AppLayout><PickupMode /></AppLayout>} />
          <Route path="/map" element={<MapPage />} />
          <Route path="/lockbox" element={<AppLayout><Lockbox /></AppLayout>} />
          <Route path="/list" element={<AppLayout><ShoppingList /></AppLayout>} />
          <Route path="/task-complete" element={<AppLayout><TaskComplete /></AppLayout>} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;

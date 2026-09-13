import { useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";

import { ControlRoomProvider } from "./app/control-room-context";
import { AppShell } from "./components/app-shell";
import { CoveragePage } from "./pages/coverage-page";
import { DecisionsPage } from "./pages/decisions-page";
import { DemoPage } from "./pages/demo-page";
import { OverviewPage } from "./pages/overview-page";
import { PackagesPage } from "./pages/packages-page";
import { ProfilePage } from "./pages/profile-page";
import { RadarPage } from "./pages/radar-page";

export function App() {
  return (
    <BrowserRouter>
      <ControlRoomProvider>
        <RouteScrollReset />
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<OverviewPage />} />
            <Route path="radar" element={<RadarPage />} />
            <Route path="packages" element={<PackagesPage />} />
            <Route path="decisions" element={<DecisionsPage />} />
            <Route path="coverage" element={<CoveragePage />} />
            <Route path="demo" element={<DemoPage />} />
            <Route path="profile" element={<ProfilePage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </ControlRoomProvider>
    </BrowserRouter>
  );
}

function RouteScrollReset() {
  const { pathname } = useLocation();
  useEffect(() => {
    document.documentElement.scrollTop = 0;
    document.body.scrollTop = 0;
  }, [pathname]);
  return null;
}

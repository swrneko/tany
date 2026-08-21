import { Box, CircularProgress } from "@mui/material";
import { useCallback, useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { api, type SetupStatus, type User } from "./api/client";
import { AppShell } from "./components/AppShell";
import { JobsPage } from "./pages/JobsPage";
import { LoginPage } from "./pages/LoginPage";
import { PresetsPage } from "./pages/PresetsPage";
import { SetupPage } from "./pages/SetupPage";
import { TranscriptPage } from "./pages/TranscriptPage";

export default function App() {
  const [status, setStatus] = useState<SetupStatus | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  const bootstrap = useCallback(async () => {
    const next = await api.setupStatus();
    setStatus(next);
    if (!next.needs_setup) {
      setUser(await api.me().catch(() => null));
    }
    setReady(true);
  }, []);

  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  const logout = async () => {
    await api.logout();
    setUser(null);
  };

  if (!ready || !status) {
    return (
      <Box sx={{ minHeight: "100dvh", display: "grid", placeItems: "center" }}>
        <CircularProgress />
      </Box>
    );
  }

  if (status.needs_setup) {
    return (
      <SetupPage
        onCreated={() => {
          void bootstrap();
        }}
      />
    );
  }

  if (!user) {
    return <LoginPage onLoggedIn={setUser} />;
  }

  return (
    <BrowserRouter>
      <AppShell
        authMode={status.auth_mode}
        onLogout={() => {
          void logout();
        }}
      >
        <Routes>
          <Route path="/" element={<JobsPage />} />
          <Route path="/jobs/:jobId" element={<TranscriptPage />} />
          <Route path="/presets" element={<PresetsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AppShell>
    </BrowserRouter>
  );
}

import { Box, CircularProgress } from "@mui/material";
import { useCallback, useEffect, useState } from "react";

import { api, type SetupStatus, type User } from "./api/client";
import { HomePage } from "./pages/HomePage";
import { LoginPage } from "./pages/LoginPage";
import { SetupPage } from "./pages/SetupPage";

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
    <HomePage
      user={user}
      authMode={status.auth_mode}
      onLogout={() => {
        void logout();
      }}
    />
  );
}

import { Alert, Button, Stack, TextField } from "@mui/material";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { api, type User } from "../api/client";
import { AuthLayout } from "../components/AuthLayout";
import { useApiErrorMessage } from "../useApiError";

export function LoginPage({ onLoggedIn }: { onLoggedIn: (user: User) => void }) {
  const { t } = useTranslation();
  const describe = useApiErrorMessage();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onLoggedIn(await api.login(username, password));
    } catch (cause) {
      setError(describe(cause));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthLayout title={t("login.title")} subtitle={t("app.tagline")}>
      <Stack component="form" spacing={2} onSubmit={submit}>
        {error && <Alert severity="error">{error}</Alert>}

        <TextField
          label={t("login.username")}
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          autoComplete="username"
          autoFocus
          required
        />
        <TextField
          label={t("login.password")}
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          autoComplete="current-password"
          required
        />

        <Button type="submit" variant="contained" size="large" disabled={busy}>
          {t("login.submit")}
        </Button>
      </Stack>
    </AuthLayout>
  );
}

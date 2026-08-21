import { Alert, Button, Stack, TextField } from "@mui/material";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { api, type User } from "../api/client";
import { AuthLayout } from "../components/AuthLayout";
import { useApiErrorMessage } from "../useApiError";

const MIN_PASSWORD_LENGTH = 8;

export function SetupPage({ onCreated }: { onCreated: (user: User) => void }) {
  const { t } = useTranslation();
  const describe = useApiErrorMessage();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const mismatch = confirmation.length > 0 && confirmation !== password;
  const canSubmit =
    username.length >= 3 && password.length >= MIN_PASSWORD_LENGTH && !mismatch && !busy;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onCreated(await api.createFirstAdmin(username, password));
    } catch (cause) {
      setError(describe(cause));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthLayout title={t("setup.title")} subtitle={t("setup.subtitle")}>
      <Stack component="form" spacing={2} onSubmit={submit}>
        {error && <Alert severity="error">{error}</Alert>}

        <TextField
          label={t("setup.username")}
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          autoComplete="username"
          autoFocus
          required
        />
        <TextField
          label={t("setup.password")}
          helperText={t("setup.passwordHint")}
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          autoComplete="new-password"
          required
        />
        <TextField
          label={t("setup.confirm")}
          type="password"
          value={confirmation}
          onChange={(event) => setConfirmation(event.target.value)}
          error={mismatch}
          helperText={mismatch ? t("setup.passwordsDiffer") : " "}
          autoComplete="new-password"
          required
        />

        <Button type="submit" variant="contained" size="large" disabled={!canSubmit}>
          {t("setup.submit")}
        </Button>
      </Stack>
    </AuthLayout>
  );
}

import LogoutIcon from "@mui/icons-material/Logout";
import { Alert, AppBar, Box, Button, Container, Toolbar, Typography } from "@mui/material";
import { useTranslation } from "react-i18next";

import type { AuthMode, User } from "../api/client";
import { LanguageSwitch } from "../components/LanguageSwitch";

interface HomePageProps {
  user: User;
  authMode: AuthMode;
  onLogout: () => void;
}

export function HomePage({ user, authMode, onLogout }: HomePageProps) {
  const { t } = useTranslation();

  return (
    <Box sx={{ minHeight: "100dvh" }}>
      <AppBar position="static" color="transparent" elevation={0}>
        <Toolbar sx={{ gap: 2 }}>
          <Typography variant="h6" sx={{ flexGrow: 1, fontWeight: 700 }}>
            {t("app.name")}
          </Typography>
          <LanguageSwitch />
          {authMode === "builtin" && (
            <Button startIcon={<LogoutIcon />} onClick={onLogout}>
              {t("home.logout")}
            </Button>
          )}
        </Toolbar>
      </AppBar>

      <Container maxWidth="md" sx={{ py: 4, display: "grid", gap: 3 }}>
        {authMode === "disabled" && <Alert severity="warning">{t("authDisabled.banner")}</Alert>}

        <Typography variant="body2" color="text.secondary">
          {t("home.greeting", { username: user.username })}
        </Typography>
        <Typography color="text.secondary">{t("home.empty")}</Typography>
      </Container>
    </Box>
  );
}

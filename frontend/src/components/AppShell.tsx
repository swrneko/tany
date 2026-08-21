import LogoutIcon from "@mui/icons-material/Logout";
import { Alert, AppBar, Box, Button, Container, Toolbar, Typography } from "@mui/material";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import type { AuthMode } from "../api/client";
import { LanguageSwitch } from "./LanguageSwitch";

interface AppShellProps {
  authMode: AuthMode;
  onLogout: () => void;
  children: ReactNode;
}

export function AppShell({ authMode, onLogout, children }: AppShellProps) {
  const { t } = useTranslation();

  return (
    <Box sx={{ minHeight: "100dvh" }}>
      <AppBar position="sticky" color="transparent" elevation={0}>
        <Toolbar sx={{ gap: 2 }}>
          <Typography
            component={Link}
            to="/"
            variant="h6"
            sx={{ flexGrow: 1, fontWeight: 700, color: "inherit", textDecoration: "none" }}
          >
            {t("app.name")}
          </Typography>
          <Button component={Link} to="/presets" color="inherit">
            {t("presets.title")}
          </Button>
          <LanguageSwitch />
          {authMode === "builtin" && (
            <Button startIcon={<LogoutIcon />} onClick={onLogout}>
              {t("home.logout")}
            </Button>
          )}
        </Toolbar>
      </AppBar>

      <Container maxWidth="md" sx={{ py: 3, display: "grid", gap: 3 }}>
        {authMode === "disabled" && <Alert severity="warning">{t("authDisabled.banner")}</Alert>}
        {children}
      </Container>
    </Box>
  );
}

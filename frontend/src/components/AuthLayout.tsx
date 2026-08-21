import { Box, Paper, Stack, Typography } from "@mui/material";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { LanguageSwitch } from "./LanguageSwitch";

interface AuthLayoutProps {
  title: string;
  subtitle?: string;
  children: ReactNode;
}

export function AuthLayout({ title, subtitle, children }: AuthLayoutProps) {
  const { t } = useTranslation();

  return (
    <Box
      sx={{
        minHeight: "100dvh",
        display: "grid",
        placeItems: "center",
        p: 2,
        background: (theme) =>
          `radial-gradient(120% 80% at 50% 0%, ${(theme.vars ?? theme).palette.primary.main}22, transparent 70%)`,
      }}
    >
      <Stack spacing={2} sx={{ width: "100%", maxWidth: 420 }}>
        <Stack direction="row" sx={{ alignItems: "center", justifyContent: "space-between" }}>
          <Typography variant="overline" color="text.secondary">
            {t("app.name")}
          </Typography>
          <LanguageSwitch />
        </Stack>

        <Paper elevation={0} sx={{ p: 4, borderRadius: 6 }}>
          <Typography variant="h5" gutterBottom sx={{ fontWeight: 700 }}>
            {title}
          </Typography>
          {subtitle && (
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              {subtitle}
            </Typography>
          )}
          {children}
        </Paper>
      </Stack>
    </Box>
  );
}

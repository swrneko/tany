import TranslateIcon from "@mui/icons-material/Translate";
import { MenuItem, TextField } from "@mui/material";
import { useTranslation } from "react-i18next";

import { SUPPORTED_LANGUAGES } from "../i18n";

export function LanguageSwitch() {
  const { i18n, t } = useTranslation();
  const current = SUPPORTED_LANGUAGES.find((lng) => i18n.resolvedLanguage === lng) ?? "en";

  return (
    <TextField
      select
      size="small"
      variant="standard"
      value={current}
      onChange={(event) => void i18n.changeLanguage(event.target.value)}
      aria-label={t("language.label")}
      slotProps={{
        input: {
          disableUnderline: true,
          startAdornment: <TranslateIcon fontSize="small" sx={{ mr: 1, opacity: 0.7 }} />,
        },
      }}
    >
      {SUPPORTED_LANGUAGES.map((lng) => (
        <MenuItem key={lng} value={lng}>
          {t(`language.${lng}`)}
        </MenuItem>
      ))}
    </TextField>
  );
}

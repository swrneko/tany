import {
  argbFromHex,
  hexFromArgb,
  themeFromSourceColor,
  type Scheme,
} from "@material/material-color-utilities";
import { createTheme } from "@mui/material/styles";

/**
 * MUI ships no Material 3 Expressive implementation, so the M3 look is built
 * here: a tonal palette generated from one seed colour, generous radii, and
 * full-height shape on interactive surfaces.
 */
const SEED_COLOR = "#6750A4";

const m3 = themeFromSourceColor(argbFromHex(SEED_COLOR));

const paletteFrom = (scheme: Scheme) => ({
  primary: {
    main: hexFromArgb(scheme.primary),
    contrastText: hexFromArgb(scheme.onPrimary),
  },
  secondary: {
    main: hexFromArgb(scheme.secondary),
    contrastText: hexFromArgb(scheme.onSecondary),
  },
  error: {
    main: hexFromArgb(scheme.error),
    contrastText: hexFromArgb(scheme.onError),
  },
  background: {
    default: hexFromArgb(scheme.background),
    paper: hexFromArgb(scheme.surface),
  },
  text: {
    primary: hexFromArgb(scheme.onSurface),
    secondary: hexFromArgb(scheme.onSurfaceVariant),
  },
  divider: hexFromArgb(scheme.outlineVariant),
});

export const theme = createTheme({
  cssVariables: { colorSchemeSelector: "data" },
  colorSchemes: {
    light: { palette: paletteFrom(m3.schemes.light) },
    dark: { palette: paletteFrom(m3.schemes.dark) },
  },
  shape: { borderRadius: 16 },
  typography: {
    fontFamily: 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
    button: { textTransform: "none", fontWeight: 600 },
  },
  components: {
    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: {
        root: { borderRadius: 999, minHeight: 40, paddingInline: 24 },
      },
    },
    MuiTextField: { defaultProps: { variant: "filled" } },
    MuiFilledInput: {
      styleOverrides: {
        root: { borderRadius: 12, "&::before, &::after": { display: "none" } },
      },
    },
    MuiPaper: { styleOverrides: { root: { backgroundImage: "none" } } },
  },
});

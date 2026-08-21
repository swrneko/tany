import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutlined";
import {
  Alert,
  Box,
  Button,
  Chip,
  IconButton,
  LinearProgress,
  MenuItem,
  Paper,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { api, TERMINAL_STATUSES, type Preset, type Summary } from "../api/client";
import { useApiErrorMessage, useCodeMessage } from "../useApiError";
import { usePresetLabel } from "../usePresetLabel";

export function SummaryPanel({ jobId }: { jobId: string }) {
  const { t } = useTranslation();
  const describe = useApiErrorMessage();
  const describeCode = useCodeMessage();
  const label = usePresetLabel();

  const [presets, setPresets] = useState<Preset[]>([]);
  const [chosen, setChosen] = useState("");
  const [summaries, setSummaries] = useState<Summary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setSummaries(await api.listSummaries(jobId));
  }, [jobId]);

  useEffect(() => {
    void api.listPresets().then((loaded) => {
      setPresets(loaded);
      setChosen((current) => current || (loaded[0]?.id ?? ""));
    });
    void refresh();
  }, [refresh]);

  // One stream per unfinished summary. Unlike the job list this stays at one or
  // two at a time: a summary is asked for by hand, one click at a time.
  const pending = summaries.filter((summary) => !TERMINAL_STATUSES.includes(summary.status));
  const pendingIds = pending.map((summary) => summary.id).join(",");
  useEffect(() => {
    if (!pendingIds) return;
    const closers = pendingIds.split(",").map((id) =>
      api.watchSummary(id, (updated) =>
        setSummaries((current) =>
          current.map((summary) => (summary.id === updated.id ? updated : summary)),
        ),
      ),
    );
    return () => closers.forEach((close) => close());
  }, [pendingIds]);

  const summarise = async () => {
    setError(null);
    try {
      await api.createSummary(jobId, chosen);
      await refresh();
    } catch (cause) {
      setError(describe(cause));
    }
  };

  const remove = async (summary: Summary) => {
    await api.deleteSummary(summary.id);
    await refresh();
  };

  const copy = async (summary: Summary) => {
    await navigator.clipboard.writeText(summary.content);
    setCopied(summary.id);
    setTimeout(() => setCopied(null), 2000);
  };

  return (
    <Stack spacing={2}>
      <Typography variant="h6" sx={{ fontWeight: 700 }}>
        {t("summary.title")}
      </Typography>

      {error && <Alert severity="error">{error}</Alert>}

      <Stack direction="row" spacing={1} sx={{ alignItems: "flex-start", flexWrap: "wrap" }}>
        <TextField
          select
          size="small"
          label={t("summary.preset")}
          value={chosen}
          onChange={(event) => setChosen(event.target.value)}
          sx={{ minWidth: 260 }}
          helperText={presets.find((preset) => preset.id === chosen)?.builtin_key
            ? label(presets.find((preset) => preset.id === chosen)!).description
            : " "}
        >
          {presets.map((preset) => (
            <MenuItem key={preset.id} value={preset.id}>
              {label(preset).name}
            </MenuItem>
          ))}
        </TextField>

        <Button
          variant="contained"
          startIcon={<AutoAwesomeIcon />}
          onClick={() => void summarise()}
          disabled={!chosen}
          sx={{ mt: 0.5 }}
        >
          {t("summary.run")}
        </Button>
      </Stack>

      {summaries.length === 0 && (
        <Typography color="text.secondary">{t("summary.empty")}</Typography>
      )}

      {summaries.map((summary) => (
        <Paper key={summary.id} elevation={0} sx={{ p: 3, borderRadius: 6 }}>
          <Stack
            direction="row"
            sx={{ alignItems: "center", justifyContent: "space-between", gap: 1, mb: 1 }}
          >
            <Stack direction="row" sx={{ alignItems: "center", gap: 1, flexWrap: "wrap" }}>
              <Typography sx={{ fontWeight: 600 }}>{summary.preset_name}</Typography>
              {summary.model_used && <Chip size="small" label={summary.model_used} />}
              {!TERMINAL_STATUSES.includes(summary.status) && (
                <Chip size="small" color="info" label={t(`jobs.status.${summary.status}`)} />
              )}
            </Stack>

            <Stack direction="row" sx={{ gap: 0.5 }}>
              <IconButton size="small" onClick={() => void copy(summary)}>
                <ContentCopyIcon fontSize="small" />
              </IconButton>
              <IconButton size="small" onClick={() => void remove(summary)}>
                <DeleteOutlineIcon fontSize="small" />
              </IconButton>
            </Stack>
          </Stack>

          {copied === summary.id && (
            <Typography variant="caption" color="success.main">
              {t("transcript.copied")}
            </Typography>
          )}

          {summary.status === "failed" ? (
            <Alert severity="error">
              {describeCode(summary.error_code, summary.error_params)}
            </Alert>
          ) : (
            <>
              {!TERMINAL_STATUSES.includes(summary.status) && (
                <LinearProgress
                  variant={summary.progress > 0 ? "determinate" : "indeterminate"}
                  value={summary.progress * 100}
                  sx={{ mb: 1, borderRadius: 1 }}
                />
              )}
              <Box sx={{ whiteSpace: "pre-wrap" }}>
                <Typography component="div">{summary.content}</Typography>
              </Box>
            </>
          )}
        </Paper>
      ))}
    </Stack>
  );
}

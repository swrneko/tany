import UploadFileIcon from "@mui/icons-material/UploadFile";
import {
  Alert,
  Box,
  Chip,
  LinearProgress,
  List,
  ListItemButton,
  ListItemText,
  Paper,
  Stack,
  Typography,
} from "@mui/material";
import { useCallback, useEffect, useRef, useState, type DragEvent } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { api, type Job, type JobStatus } from "../api/client";
import { useApiErrorMessage, useCodeMessage } from "../useApiError";

const POLL_INTERVAL_MS = 2000;

const STATUS_COLOR: Record<JobStatus, "default" | "info" | "success" | "error"> = {
  queued: "default",
  running: "info",
  done: "success",
  failed: "error",
};

export function JobsPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const describe = useApiErrorMessage();
  const describeCode = useCodeMessage();
  const input = useRef<HTMLInputElement>(null);

  const [jobs, setJobs] = useState<Job[] | null>(null);
  const [uploading, setUploading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [hasProvider, setHasProvider] = useState(true);

  const refresh = useCallback(async () => {
    setJobs(await api.listJobs());
  }, []);

  useEffect(() => {
    void refresh();
    void api
      .listProviders()
      .then((providers) => setHasProvider(providers.some((p) => p.kind === "stt")));
  }, [refresh]);

  // Polling, not SSE — live progress is the next milestone, and a two-second
  // poll on a list of a few dozen rows costs nothing until then.
  const pending = jobs?.some((job) => job.status === "queued" || job.status === "running");
  useEffect(() => {
    if (!pending) return;
    const timer = setInterval(() => void refresh(), POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [pending, refresh]);

  const upload = async (file: File) => {
    setUploading(file.name);
    setError(null);
    try {
      await api.uploadJob(file);
      await refresh();
    } catch (cause) {
      setError(describe(cause));
    } finally {
      setUploading(null);
    }
  };

  const onDrop = (event: DragEvent) => {
    event.preventDefault();
    const file = event.dataTransfer.files[0];
    if (file) void upload(file);
  };

  return (
    <Stack spacing={3}>
      <Typography variant="h5" sx={{ fontWeight: 700 }}>
        {t("jobs.title")}
      </Typography>

      {!hasProvider && <Alert severity="warning">{t("jobs.noProvider")}</Alert>}
      {error && <Alert severity="error">{error}</Alert>}

      <Paper
        elevation={0}
        onClick={() => input.current?.click()}
        onDrop={onDrop}
        onDragOver={(event) => event.preventDefault()}
        sx={{
          p: 5,
          borderRadius: 6,
          border: "2px dashed",
          borderColor: "divider",
          textAlign: "center",
          cursor: "pointer",
          "&:hover": { borderColor: "primary.main" },
        }}
      >
        <UploadFileIcon sx={{ fontSize: 40, opacity: 0.6 }} />
        <Typography color="text.secondary" sx={{ mt: 1 }}>
          {uploading ? t("jobs.uploading", { name: uploading }) : t("jobs.drop")}
        </Typography>
        {uploading && <LinearProgress sx={{ mt: 2, borderRadius: 1 }} />}
        <input
          ref={input}
          type="file"
          hidden
          accept="audio/*,video/*"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void upload(file);
            event.target.value = "";
          }}
        />
      </Paper>

      {jobs && jobs.length === 0 && (
        <Typography color="text.secondary">{t("jobs.empty")}</Typography>
      )}

      {jobs && jobs.length > 0 && (
        <Paper elevation={0} sx={{ borderRadius: 6, overflow: "hidden" }}>
          <List disablePadding>
            {jobs.map((job) => (
              <ListItemButton
                key={job.id}
                divider
                onClick={() => navigate(`/jobs/${job.id}`)}
                disabled={job.status === "queued" || job.status === "running"}
              >
                <ListItemText
                  primary={job.title}
                  secondary={
                    job.status === "failed"
                      ? describeCode(job.error_code, job.error_params)
                      : formatMeta(job)
                  }
                />
                <Box sx={{ ml: 2 }}>
                  <Chip
                    size="small"
                    label={t(`jobs.status.${job.status}`)}
                    color={STATUS_COLOR[job.status]}
                  />
                </Box>
              </ListItemButton>
            ))}
          </List>
        </Paper>
      )}
    </Stack>
  );
}

function formatMeta(job: Job): string {
  if (job.duration_sec === null) return new Date(job.created_at).toLocaleString();
  const minutes = Math.floor(job.duration_sec / 60);
  const seconds = Math.round(job.duration_sec % 60);
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

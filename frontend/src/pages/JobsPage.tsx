import CloseIcon from "@mui/icons-material/Close";
import UploadFileIcon from "@mui/icons-material/UploadFile";
import {
  Alert,
  Box,
  Chip,
  IconButton,
  LinearProgress,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  Paper,
  Stack,
  Tooltip,
  Typography,
} from "@mui/material";
import { useCallback, useEffect, useRef, useState, type DragEvent, type MouseEvent } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { api, TERMINAL_STATUSES, type Job, type JobStatus } from "../api/client";
import { useApiErrorMessage, useCodeMessage } from "../useApiError";

const STATUS_COLOR: Record<JobStatus, "default" | "info" | "success" | "error"> = {
  queued: "default",
  running: "info",
  cancelling: "default",
  cancelled: "default",
  done: "success",
  failed: "error",
};

const isPending = (job: Job) => !TERMINAL_STATUSES.includes(job.status);

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

  // Reopened whenever work starts: the server ends the stream once everything
  // is terminal, so an idle page holds no connection at all.
  const pendingCount = jobs?.filter(isPending).length ?? 0;
  useEffect(() => {
    if (pendingCount === 0) return;
    return api.watchJobs(setJobs);
  }, [pendingCount]);

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

  const cancel = async (event: MouseEvent, job: Job) => {
    event.stopPropagation();
    try {
      await api.cancelJob(job.id);
      await refresh();
    } catch (cause) {
      setError(describe(cause));
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
              <ListItem
                key={job.id}
                divider
                disablePadding
                secondaryAction={
                  <Stack direction="row" sx={{ alignItems: "center", gap: 1 }}>
                    {job.status === "running" && (
                      <Box sx={{ width: 80 }}>
                        <LinearProgress
                          variant={job.progress > 0 ? "determinate" : "indeterminate"}
                          value={job.progress * 100}
                          sx={{ borderRadius: 1 }}
                        />
                      </Box>
                    )}
                    <Chip
                      size="small"
                      label={t(`jobs.status.${job.status}`)}
                      color={STATUS_COLOR[job.status]}
                    />
                    {isPending(job) && job.status !== "cancelling" && (
                      <Tooltip title={t("jobs.cancel")}>
                        <IconButton size="small" onClick={(event) => void cancel(event, job)}>
                          <CloseIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    )}
                  </Stack>
                }
              >
                <ListItemButton
                  onClick={() => navigate(`/jobs/${job.id}`)}
                  disabled={job.status !== "done"}
                  sx={{ py: 1.5, pr: 24 }}
                >
                  <ListItemText
                    primary={job.title}
                    secondary={
                      job.status === "failed"
                        ? describeCode(job.error_code, job.error_params)
                        : formatMeta(job)
                    }
                  />
                </ListItemButton>
              </ListItem>
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

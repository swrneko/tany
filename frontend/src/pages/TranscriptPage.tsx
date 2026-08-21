import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Paper,
  Stack,
  Switch,
  Typography,
} from "@mui/material";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";

import { api, type Job, type Transcript } from "../api/client";
import { useApiErrorMessage } from "../useApiError";

export function TranscriptPage() {
  const { jobId = "" } = useParams();
  const { t } = useTranslation();
  const describe = useApiErrorMessage();

  const [job, setJob] = useState<Job | null>(null);
  const [transcript, setTranscript] = useState<Transcript | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showTimestamps, setShowTimestamps] = useState(true);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    Promise.all([api.readJob(jobId), api.readTranscript(jobId)])
      .then(([loadedJob, loadedTranscript]) => {
        setJob(loadedJob);
        setTranscript(loadedTranscript);
      })
      .catch((cause: unknown) => setError(describe(cause)));
    // describe is recreated on every language change; refetching then is wasteful.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  const copy = async () => {
    if (!transcript) return;
    await navigator.clipboard.writeText(transcript.text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (error) {
    return (
      <Stack spacing={2}>
        <BackLink />
        <Alert severity="error">{error}</Alert>
      </Stack>
    );
  }

  if (!job || !transcript) {
    return (
      <Box sx={{ display: "grid", placeItems: "center", py: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Stack spacing={3}>
      <BackLink />

      <Stack
        direction="row"
        sx={{ alignItems: "center", justifyContent: "space-between", gap: 2, flexWrap: "wrap" }}
      >
        <Box>
          <Typography variant="h5" sx={{ fontWeight: 700 }}>
            {job.title}
          </Typography>
          {transcript.language && (
            <Typography variant="body2" color="text.secondary">
              {t("transcript.language", { language: transcript.language })}
            </Typography>
          )}
        </Box>

        <Stack direction="row" sx={{ alignItems: "center", gap: 1 }}>
          <Typography variant="body2" color="text.secondary">
            {t("transcript.timestamps")}
          </Typography>
          <Switch
            checked={showTimestamps}
            onChange={(event) => setShowTimestamps(event.target.checked)}
          />
          <Button startIcon={<ContentCopyIcon />} onClick={() => void copy()}>
            {copied ? t("transcript.copied") : t("transcript.copy")}
          </Button>
        </Stack>
      </Stack>

      <Paper elevation={0} sx={{ p: 3, borderRadius: 6 }}>
        <Stack spacing={1.5}>
          {transcript.segments.map((segment) => (
            <Stack key={segment.idx} direction="row" spacing={2}>
              {showTimestamps && (
                <Typography
                  variant="body2"
                  color="text.secondary"
                  sx={{ fontVariantNumeric: "tabular-nums", minWidth: 64, pt: 0.25 }}
                >
                  {formatTimestamp(segment.start)}
                </Typography>
              )}
              <Typography>{segment.text}</Typography>
            </Stack>
          ))}
        </Stack>
      </Paper>
    </Stack>
  );
}

function BackLink() {
  const { t } = useTranslation();
  return (
    <Button component={Link} to="/" startIcon={<ArrowBackIcon />} sx={{ alignSelf: "start" }}>
      {t("transcript.back")}
    </Button>
  );
}

function formatTimestamp(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const rest = Math.floor(seconds % 60);
  return `${minutes}:${String(rest).padStart(2, "0")}`;
}

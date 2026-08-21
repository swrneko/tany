import AddIcon from "@mui/icons-material/Add";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutlined";
import EditIcon from "@mui/icons-material/Edit";
import {
  Alert,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  List,
  ListItem,
  ListItemText,
  Paper,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { api, type Preset, type PresetDraft } from "../api/client";
import { useApiErrorMessage } from "../useApiError";
import { usePresetLabel } from "../usePresetLabel";

const BLANK: PresetDraft = {
  name: "",
  description: "",
  system_prompt: "",
  user_template: "{transcript}",
  model_override: null,
  provider_id: null,
  temperature: 0.3,
  output_format: "markdown",
};

const toDraft = (preset: Preset): PresetDraft => ({
  name: preset.name,
  description: preset.description,
  system_prompt: preset.system_prompt,
  user_template: preset.user_template,
  model_override: preset.model_override,
  provider_id: preset.provider_id,
  temperature: preset.temperature,
  output_format: preset.output_format,
});

export function PresetsPage() {
  const { t } = useTranslation();
  const describe = useApiErrorMessage();
  const label = usePresetLabel();

  const [presets, setPresets] = useState<Preset[]>([]);
  const [editing, setEditing] = useState<{ id: string | null; draft: PresetDraft } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setPresets(await api.listPresets());
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const save = async () => {
    if (!editing) return;
    setError(null);
    try {
      if (editing.id) {
        await api.updatePreset(editing.id, editing.draft);
      } else {
        await api.createPreset(editing.draft);
      }
      setEditing(null);
      await refresh();
    } catch (cause) {
      setError(describe(cause));
    }
  };

  const remove = async (preset: Preset) => {
    try {
      await api.deletePreset(preset.id);
      await refresh();
    } catch (cause) {
      setError(describe(cause));
    }
  };

  return (
    <Stack spacing={3}>
      <Stack direction="row" sx={{ alignItems: "center", justifyContent: "space-between" }}>
        <Typography variant="h5" sx={{ fontWeight: 700 }}>
          {t("presets.title")}
        </Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => setEditing({ id: null, draft: BLANK })}
        >
          {t("presets.new")}
        </Button>
      </Stack>

      {error && <Alert severity="error">{error}</Alert>}

      <Paper elevation={0} sx={{ borderRadius: 6, overflow: "hidden" }}>
        <List disablePadding>
          {presets.map((preset) => {
            const { name, description } = label(preset);
            return (
              <ListItem
                key={preset.id}
                divider
                secondaryAction={
                  <Stack direction="row" sx={{ gap: 0.5 }}>
                    {preset.is_builtin ? (
                      <Tooltip title={t("presets.duplicate")}>
                        <IconButton
                          size="small"
                          onClick={() =>
                            setEditing({
                              id: null,
                              draft: {
                                ...toDraft(preset),
                                name: t("presets.copyOf", { name }),
                              },
                            })
                          }
                        >
                          <ContentCopyIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    ) : (
                      <>
                        <IconButton
                          size="small"
                          onClick={() => setEditing({ id: preset.id, draft: toDraft(preset) })}
                        >
                          <EditIcon fontSize="small" />
                        </IconButton>
                        <IconButton size="small" onClick={() => void remove(preset)}>
                          <DeleteOutlineIcon fontSize="small" />
                        </IconButton>
                      </>
                    )}
                  </Stack>
                }
              >
                <ListItemText
                  primary={
                    <Stack direction="row" sx={{ alignItems: "center", gap: 1 }}>
                      <span>{name}</span>
                      {preset.is_builtin && (
                        <Chip size="small" variant="outlined" label={t("presets.builtinTag")} />
                      )}
                    </Stack>
                  }
                  secondary={description}
                  sx={{ pr: 12 }}
                />
              </ListItem>
            );
          })}
        </List>
      </Paper>

      <Dialog open={editing !== null} onClose={() => setEditing(null)} fullWidth maxWidth="sm">
        <DialogTitle>{editing?.id ? t("presets.edit") : t("presets.new")}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <TextField
              label={t("presets.name")}
              value={editing?.draft.name ?? ""}
              onChange={(event) =>
                setEditing((current) =>
                  current ? { ...current, draft: { ...current.draft, name: event.target.value } } : current,
                )
              }
              required
            />
            <TextField
              label={t("presets.description")}
              value={editing?.draft.description ?? ""}
              onChange={(event) =>
                setEditing((current) =>
                  current
                    ? { ...current, draft: { ...current.draft, description: event.target.value } }
                    : current,
                )
              }
            />
            <TextField
              label={t("presets.systemPrompt")}
              multiline
              minRows={3}
              value={editing?.draft.system_prompt ?? ""}
              onChange={(event) =>
                setEditing((current) =>
                  current
                    ? { ...current, draft: { ...current.draft, system_prompt: event.target.value } }
                    : current,
                )
              }
              required
            />
            <TextField
              label={t("presets.userTemplate")}
              helperText={t("presets.templateHint")}
              multiline
              minRows={4}
              value={editing?.draft.user_template ?? ""}
              onChange={(event) =>
                setEditing((current) =>
                  current
                    ? { ...current, draft: { ...current.draft, user_template: event.target.value } }
                    : current,
                )
              }
              required
            />
            <TextField
              label={t("presets.temperature")}
              type="number"
              slotProps={{ htmlInput: { step: 0.1, min: 0, max: 2 } }}
              value={editing?.draft.temperature ?? 0.3}
              onChange={(event) =>
                setEditing((current) =>
                  current
                    ? {
                        ...current,
                        draft: { ...current.draft, temperature: Number(event.target.value) },
                      }
                    : current,
                )
              }
            />
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setEditing(null)}>{t("presets.cancel")}</Button>
          <Button variant="contained" onClick={() => void save()}>
            {t("presets.save")}
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}

import { useTranslation } from "react-i18next";

import type { Preset } from "./api/client";

/** Built-in presets are shipped in English and translated here from a stable
 * key. Presets the user wrote are shown exactly as they wrote them. */
export function usePresetLabel(): (preset: Preset) => { name: string; description: string } {
  const { t } = useTranslation();

  return (preset: Preset) => {
    if (!preset.builtin_key) {
      return { name: preset.name, description: preset.description ?? "" };
    }
    return {
      name: t([`presets.builtin.${preset.builtin_key}.name`, preset.name]),
      description: t([
        `presets.builtin.${preset.builtin_key}.description`,
        preset.description ?? "",
      ]),
    };
  };
}

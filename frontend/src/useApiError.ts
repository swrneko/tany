import { useTranslation } from "react-i18next";

import { ApiError } from "./api/client";

type Params = Record<string, unknown>;

/** Renders an error code in the user's language.
 *
 * Codes arrive both from failed requests and from finished jobs that carry a
 * stored failure, so the translation step works on the code, not on an
 * exception type. */
export function useCodeMessage(): (code: string | null, params?: Params) => string {
  const { t } = useTranslation();

  return (code, params = {}) =>
    code ? t([`errors.${code}`, "errors.unknown"], params) : t("errors.unknown");
}

export function useApiErrorMessage(): (error: unknown) => string {
  const describeCode = useCodeMessage();

  return (error: unknown) =>
    error instanceof ApiError ? describeCode(error.code, error.params) : describeCode(null);
}

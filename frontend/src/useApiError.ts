import { useTranslation } from "react-i18next";

import { ApiError } from "./api/client";

/** Turns an error code from the API into a message in the user's language. */
export function useApiErrorMessage(): (error: unknown) => string {
  const { t } = useTranslation();

  return (error: unknown) => {
    const code = error instanceof ApiError ? error.code : "unknown";
    return t([`errors.${code}`, "errors.unknown"]);
  };
}

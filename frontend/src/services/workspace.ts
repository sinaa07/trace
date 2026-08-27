const ACTIVE_CASE_KEY = "trace.activeCaseId";

export function getActiveCaseId(): string {
  try {
    return localStorage.getItem(ACTIVE_CASE_KEY) ?? "";
  } catch {
    return "";
  }
}

export function setActiveCaseId(caseId: string): void {
  try {
    if (caseId) {
      localStorage.setItem(ACTIVE_CASE_KEY, caseId);
    } else {
      localStorage.removeItem(ACTIVE_CASE_KEY);
    }
  } catch {
    /* ignore storage failures */
  }
}

export function clearActiveCaseId(): void {
  setActiveCaseId("");
}

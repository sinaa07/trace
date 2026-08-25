const STORAGE_KEY = "trace.investigator";

export function getInvestigatorName(): string {
  return localStorage.getItem(STORAGE_KEY) ?? "";
}

export function setInvestigatorName(name: string): void {
  localStorage.setItem(STORAGE_KEY, name.trim());
}

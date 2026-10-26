export const MAX_FILE_BYTES = 10 * 1024 * 1024;
export const FILE_ACCEPT = ".pdf,.md,.txt";
const mimeTypes: Record<string, string> = {
  pdf: "application/pdf",
  md: "text/markdown",
  txt: "text/plain",
};
export function fileContentType(file: File): string | undefined {
  return mimeTypes[file.name.split(".").pop()?.toLowerCase() ?? ""];
}
export function validateFile(file: File): string | undefined {
  if (!fileContentType(file))
    return "Choose a PDF, Markdown (.md), or text (.txt) file.";
  if (!file.size || file.size > MAX_FILE_BYTES)
    return "Choose a non-empty file no larger than 10 MB.";
}
export function fileSize(bytes: number): string {
  return bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} KB`
    : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

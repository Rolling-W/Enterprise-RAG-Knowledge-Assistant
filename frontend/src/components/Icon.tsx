type IconName =
  | "sparkles"
  | "chat"
  | "folder"
  | "logout"
  | "arrow"
  | "upload"
  | "file"
  | "check"
  | "close"
  | "search"
  | "chevron"
  | "copy"
  | "plus"
  | "shield"
  | "eye"
  | "eyeOff"
  | "clock"
  | "alert";
const paths: Record<IconName, string> = {
  sparkles:
    "M12 10C9.4 7.8 6.5 7 3 7v11c3.5 0 6.4.8 9 3 2.6-2.2 5.5-3 9-3V7c-3.5 0-6.4.8-9 3ZM12 10v11M6 11l3 1M6 15l3 1M15 12l3-1M15 16l3-1M12 6c0-1.7 1.3-3 3-3h2M21 3a2 2 0 1 1-4 0 2 2 0 0 1 4 0Z",
  chat: "M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9h.5a8.5 8.5 0 0 1 8 8v.5Z",
  folder: "M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v10H3V7Z",
  logout: "M9 5H4v14h5M16 8l4 4-4 4M8 12h12",
  arrow: "M12 19V5M5 12l7-7 7 7",
  upload: "M12 16V3M7 8l5-5 5 5M4 15v6h16v-6",
  file: "M14 2H5v20h14V7l-5-5ZM14 2v5h5M8 12h8M8 16h6",
  check: "m5 12 4 4L19 6",
  close: "m6 6 12 12M6 18 18 6",
  search: "M21 21l-4.5-4.5M19 10.5a8.5 8.5 0 1 1-17 0 8.5 8.5 0 0 1 17 0Z",
  chevron: "m9 5 7 7-7 7",
  copy: "M9 9h12v12H9V9ZM15 5V3H3v12h2",
  plus: "M12 5v14M5 12h14",
  shield: "m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Zm-4 9 3 3 5-6",
  eye: "M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Zm13 0a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z",
  eyeOff:
    "m3 3 18 18M10 5a11 11 0 0 1 2 0c6 0 10 7 10 7a20 20 0 0 1-3 4M6 6a20 20 0 0 0-4 6s4 7 10 7a12 12 0 0 0 5-1",
  clock: "M12 7v5l3 2M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0Z",
  alert: "M12 8v5M12 17h.01M12 3 2 21h20L12 3Z",
};
export function Icon({
  name,
  size = 20,
  className = "",
}: {
  name: IconName;
  size?: number;
  className?: string;
}) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={paths[name]} />
    </svg>
  );
}

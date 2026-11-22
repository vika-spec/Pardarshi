type P = { size?: number; color?: string; label?: string };

const base = (size: number, label?: string) => ({
  width: size,
  height: size,
  viewBox: "0 0 24 24",
  fill: "none",
  strokeWidth: 2,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  ...(label ? { role: "img", "aria-label": label } : { "aria-hidden": true }),
});

export const Lock = ({ size = 16, color = "currentColor", label }: P) => (
  <svg {...base(size, label)} stroke={color}><rect x="5" y="11" width="14" height="10" rx="2" /><path d="M8 11V7a4 4 0 0 1 8 0v4" /></svg>
);
export const Warn = ({ size = 16, color = "currentColor", label }: P) => (
  <svg {...base(size, label)} stroke={color}><path d="M12 3l9 16H3z" /><path d="M12 10v4" /><path d="M12 17h.01" /></svg>
);
export const Check = ({ size = 16, color = "currentColor", label }: P) => (
  <svg {...base(size, label)} stroke={color} strokeWidth={2.4}><path d="M5 12l5 5 9-10" /></svg>
);
export const Dash = ({ size = 16, color = "currentColor", label }: P) => (
  <svg {...base(size, label)} stroke={color}><path d="M6 12h12" /></svg>
);
export const Close = ({ size = 18, color = "currentColor", label }: P) => (
  <svg {...base(size, label)} stroke={color}><path d="M6 6l12 12M18 6L6 18" /></svg>
);
export const Upload = ({ size = 18, color = "currentColor", label }: P) => (
  <svg {...base(size, label)} stroke={color}><path d="M12 16V4" /><path d="M7 9l5-5 5 5" /><path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" /></svg>
);
export const External = ({ size = 14, color = "currentColor", label }: P) => (
  <svg {...base(size, label)} stroke={color}><path d="M14 4h6v6" /><path d="M10 14L20 4" /><path d="M20 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h5" /></svg>
);
export const Chat = ({ size = 18, color = "currentColor", label }: P) => (
  <svg {...base(size, label)} stroke={color}><path d="M4 5h16v11H9l-5 4z" /></svg>
);
export const Send = ({ size = 18, color = "currentColor", label }: P) => (
  <svg {...base(size, label)} stroke={color}><path d="M4 12l16-8-6 16-3-7z" /></svg>
);
export const Chevron = ({ size = 14, color = "currentColor" }: P) => (
  <svg {...base(size)} stroke={color} className="chev"><path d="M9 6l6 6-6 6" /></svg>
);

export function StatusIcon({ status, size = 16 }: { status: string; size?: number }) {
  if (status === "flagged") return <Warn size={size} color="var(--red)" />;
  if (status === "passed") return <Check size={size} color="var(--green)" />;
  return <Dash size={size} color="var(--muted)" />;
}

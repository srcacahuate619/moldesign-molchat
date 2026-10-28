import type { ReactNode } from "react";

function Icon({ children }: { children: ReactNode }) {
  return <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">{children}</svg>;
}
export function BotIcon() { return <Icon><path d="M12 3v3M9 3h6"/><rect x="4" y="7" width="16" height="13" rx="4"/><path d="M2 12h2m16 0h2M9 13h.01M15 13h.01M9 17h6"/></Icon>; }
export function HistoryIcon() { return <Icon><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5M12 7v5l3 2"/></Icon>; }
export function PlusIcon() { return <Icon><path d="M12 5v14M5 12h14"/></Icon>; }
export function SendIcon() { return <Icon><path d="m3 11 18-8-8 18-2-8-8-2ZM11 13 21 3"/></Icon>; }
export function MicIcon() { return <Icon><rect x="9" y="3" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3m-4 0h8"/></Icon>; }
export function StopIcon() { return <Icon><rect x="6" y="6" width="12" height="12" rx="2"/></Icon>; }

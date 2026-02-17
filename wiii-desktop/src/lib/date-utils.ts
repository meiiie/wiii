/**
 * Date formatting utilities — Vietnamese relative time.
 * Sprint 81: Message timestamps.
 */

/**
 * Format a timestamp as relative Vietnamese time.
 * "vừa xong", "2 phút trước", "1 giờ trước", "hôm qua lúc 14:30", "12/02 lúc 09:15"
 */
export function formatRelativeTime(timestamp: string | Date): string {
  const date = typeof timestamp === "string" ? new Date(timestamp) : timestamp;
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);

  if (diffSec < 60) return "vừa xong";
  if (diffMin < 60) return `${diffMin} phút trước`;
  if (diffHour < 24 && isToday(date, now)) return `${diffHour} giờ trước`;

  const time = formatTime(date);

  if (isYesterday(date, now)) return `hôm qua lúc ${time}`;

  // Same year — show dd/MM
  if (date.getFullYear() === now.getFullYear()) {
    return `${pad(date.getDate())}/${pad(date.getMonth() + 1)} lúc ${time}`;
  }

  // Different year — show dd/MM/yyyy
  return `${pad(date.getDate())}/${pad(date.getMonth() + 1)}/${date.getFullYear()} lúc ${time}`;
}

/**
 * Format a timestamp as absolute Vietnamese time: "14/02/2026 14:30:45"
 */
export function formatAbsoluteTime(timestamp: string | Date): string {
  const date = typeof timestamp === "string" ? new Date(timestamp) : timestamp;
  return `${pad(date.getDate())}/${pad(date.getMonth() + 1)}/${date.getFullYear()} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

function formatTime(date: Date): string {
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function pad(n: number): string {
  return n < 10 ? `0${n}` : String(n);
}

function isToday(date: Date, now: Date): boolean {
  return (
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate()
  );
}

function isYesterday(date: Date, now: Date): boolean {
  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  return (
    date.getFullYear() === yesterday.getFullYear() &&
    date.getMonth() === yesterday.getMonth() &&
    date.getDate() === yesterday.getDate()
  );
}

/**
 * Time-aware Vietnamese greeting utility — Wiii personality.
 * Sprint 82: Claude Desktop-inspired greeting.
 * Sprint 111: Wiii soul — rotating warm greetings + subtitle.
 */

export type TimeOfDay = "morning" | "afternoon" | "evening";

/**
 * Determine time of day from hour (0-23).
 */
export function getTimeOfDay(hour: number): TimeOfDay {
  if (hour >= 5 && hour < 12) return "morning";
  if (hour >= 12 && hour < 18) return "afternoon";
  return "evening";
}

const GREETING_MAP: Record<TimeOfDay, string[]> = {
  morning: [
    "Chào buổi sáng",
    "Sáng nay vui quá",
    "Bình minh tươi đẹp",
  ],
  afternoon: [
    "Chào buổi chiều",
    "Chiều nay có gì hay",
    "Buổi chiều năng động",
  ],
  evening: [
    "Chào buổi tối",
    "Tối nay thư giãn nha",
    "Buổi tối an lành",
  ],
};

/** Wiii personality subtitles — rotated randomly */
const WIII_SUBTITLES: string[] = [
  "Mình ở đây, sẵn sàng giúp bạn!",
  "Hôm nay mình tìm hiểu gì nhỉ?",
  "Cùng khám phá nhé!",
  "Mình tò mò muốn giúp bạn lắm!",
  "Bạn cần gì, mình nghe đây!",
];

/**
 * Get a Vietnamese greeting based on time of day and user name.
 * Sprint 111: Returns a randomly selected greeting variant for personality.
 */
export function getGreeting(displayName?: string, hour?: number): string {
  const h = hour ?? new Date().getHours();
  const timeOfDay = getTimeOfDay(h);
  const variants = GREETING_MAP[timeOfDay];
  const base = variants[Math.floor(Math.random() * variants.length)];

  if (displayName && displayName.trim()) {
    return `${base}, ${displayName.trim()}!`;
  }
  return `${base}!`;
}

/**
 * Get a Wiii personality subtitle for the welcome screen.
 */
export function getWiiiSubtitle(): string {
  return WIII_SUBTITLES[Math.floor(Math.random() * WIII_SUBTITLES.length)];
}

/** Time-aware welcome placeholders for centered ChatInput */
const WELCOME_PLACEHOLDERS: Record<TimeOfDay, string[]> = {
  morning: [
    "Sáng nay mình tìm hiểu gì nhỉ?",
    "Hôm nay bắt đầu với câu hỏi nào?",
    "Sáng sáng, bạn muốn khám phá gì?",
  ],
  afternoon: [
    "Chiều nay mình cùng tìm hiểu nhé!",
    "Hôm nay mình tìm hiểu gì nhỉ?",
    "Chiều rồi, có câu hỏi nào không?",
  ],
  evening: [
    "Tối nay mình cùng tìm hiểu nhé!",
    "Tối rồi, bạn muốn hỏi gì không?",
    "Hôm nay mình tìm hiểu gì nhỉ?",
  ],
};

/**
 * Get a time-aware placeholder for the centered (welcome) input.
 */
export function getWelcomePlaceholder(hour?: number): string {
  const h = hour ?? new Date().getHours();
  const timeOfDay = getTimeOfDay(h);
  const variants = WELCOME_PLACEHOLDERS[timeOfDay];
  return variants[Math.floor(Math.random() * variants.length)];
}

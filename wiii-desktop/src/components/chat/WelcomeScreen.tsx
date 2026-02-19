/**
 * WelcomeScreen — Claude Desktop-inspired centered composition.
 * Sprint 82b: Staggered reveal animation, subtle background gradient,
 * refined typography following Anthropic Frontend Aesthetics Cookbook.
 */
import { useDomainStore } from "@/stores/domain-store";
import { useChatStore } from "@/stores/chat-store";
import { useSettingsStore } from "@/stores/settings-store";
import { getGreeting, getWiiiSubtitle } from "@/lib/greeting";
import { DOMAIN_ICONS } from "@/lib/domain-config";
import { WiiiAvatar } from "@/components/common/WiiiAvatar";
import { useAvatarState } from "@/hooks/useAvatarState";
import { ChatInput } from "./ChatInput";

const DOMAIN_SUGGESTIONS: Record<string, string[]> = {
  maritime: [
    "Giải thích Quy tắc 15 COLREGs",
    "SOLAS Chapter III — phương tiện cứu sinh",
    "So sánh MARPOL Annex I và VI",
  ],
  traffic_law: [
    "Mức phạt vượt đèn đỏ?",
    "Quy định nồng độ cồn?",
    "Điều kiện cấp bằng B2?",
  ],
};

interface WelcomeScreenProps {
  onSendMessage: (message: string) => void;
  onCancel: () => void;
}

export function WelcomeScreen({ onSendMessage, onCancel }: WelcomeScreenProps) {
  const { activeDomainId } = useDomainStore();
  const { createConversation, activeConversationId } = useChatStore();
  const { settings } = useSettingsStore();

  const { state: avatarState, mood: avatarMood, soulEmotion } = useAvatarState();
  const greeting = getGreeting(settings.display_name);
  const subtitle = getWiiiSubtitle();
  const suggestions = DOMAIN_SUGGESTIONS[activeDomainId] || [];

  const handleSuggestion = (question: string) => {
    if (!activeConversationId) {
      createConversation(activeDomainId);
    }
    onSendMessage(question);
  };

  return (
    <div className="flex-1 flex flex-col items-center px-6 pt-[20vh] pb-8 welcome-bg">
      <div className="w-full max-w-2xl flex flex-col items-center gap-7">
        {/* Wiii avatar — staggered reveal 1 */}
        <div className="welcome-reveal welcome-reveal-1">
          <WiiiAvatar state={avatarState} size={40} mood={avatarMood} soulEmotion={soulEmotion} />
        </div>

        {/* Greeting — staggered reveal 2: light weight, secondary color (Claude uses text-200) */}
        <h1
          className="welcome-reveal welcome-reveal-2 text-center font-normal text-text-secondary leading-[1.5]"
          style={{
            fontFamily: '"Source Serif 4", "Noto Serif", Georgia, ui-serif, serif',
            fontSize: "clamp(1.875rem, 1.2rem + 2vw, 2.5rem)",
          }}
        >
          {greeting}
        </h1>

        {/* Subtitle — staggered reveal 3: Wiii personality */}
        <p className="welcome-reveal welcome-reveal-3 -mt-4 text-[15px] font-light text-text-tertiary">
          {subtitle}
        </p>

        {/* Input Card — staggered reveal 4 */}
        <div className="welcome-reveal welcome-reveal-4 w-full">
          <ChatInput
            onSend={onSendMessage}
            onCancel={onCancel}
            centered
          />
        </div>

        {/* Suggestion chips — rounded-lg, cream bg, 0.5px border (Claude F12 exact) */}
        {suggestions.length > 0 && (
          <div className="welcome-reveal welcome-reveal-5 flex flex-wrap items-center justify-center gap-2 -mt-3">
            {suggestions.map((q, i) => {
              const DomainIcon = DOMAIN_ICONS[activeDomainId];
              return (
                <button
                  key={i}
                  onClick={() => handleSuggestion(q)}
                  className="flex items-center gap-1.5 h-8 px-2.5 rounded-lg bg-surface-secondary text-sm text-text-secondary hover:bg-surface-tertiary hover:text-text active:scale-[0.995] transition-all duration-300"
                  style={{ borderWidth: "0.5px", borderColor: "var(--border)", borderStyle: "solid" }}
                >
                  {DomainIcon && <DomainIcon size={16} className="shrink-0 text-text-tertiary" />}
                  <span className="line-clamp-1">{q}</span>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

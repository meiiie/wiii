import type {
  ArtifactBlockData,
  ContentBlock,
  PreviewBlockData,
  ScreenshotBlockData,
  SubagentGroupBlockData,
  ThinkingBlockData,
  ThinkingLevel,
  ToolExecutionBlockData,
} from "@/api/types";
import { MarkdownRenderer } from "@/components/common/MarkdownRenderer";
import { ThinkingBlock } from "./ThinkingBlock";
import { ActionText } from "./ActionText";
import { ScreenshotBlock } from "./ScreenshotBlock";
import { SubagentGroup } from "./SubagentGroup";
import { PreviewGroup } from "./PreviewGroup";
import { ArtifactCard } from "./ArtifactCard";
import { ToolExecutionStrip } from "./ToolExecutionStrip";

function normalizeText(value: string | undefined): string {
  return (value || "")
    .toLowerCase()
    .replace(/[`*_#>]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function getThinkingLead(block: ThinkingBlockData | undefined): string {
  if (!block) return "";
  const source = block.summary?.trim() || block.content?.trim() || block.label?.trim() || "";
  if (!source) return "";
  const [firstLine] = source.split(/\n+/);
  return normalizeText(firstLine);
}

function shouldHideActionBridge(blocks: ContentBlock[], index: number): boolean {
  const current = blocks[index];
  if (!current || current.type !== "action_text") return false;

  const previousThinking = [...blocks.slice(0, index)]
    .reverse()
    .find((block): block is ThinkingBlockData => block.type === "thinking");
  const nextThinking = blocks
    .slice(index + 1)
    .find((block): block is ThinkingBlockData => block.type === "thinking");

  const currentText = normalizeText(current.content);
  if (!currentText) return true;

  const previousLead = getThinkingLead(previousThinking);
  const nextLead = getThinkingLead(nextThinking);

  return Boolean(
    currentText === previousLead ||
    currentText === nextLead ||
    (previousLead && currentText.includes(previousLead)) ||
    (nextLead && currentText.includes(nextLead))
  );
}

function isThinkingContinuation(blocks: ContentBlock[], index: number): boolean {
  const current = blocks[index];
  if (!current || current.type !== "thinking" || !current.stepId) return false;

  for (let i = index - 1; i >= 0; i--) {
    const candidate = blocks[i];
    if (candidate.stepId !== current.stepId) continue;
    if (candidate.type === "thinking" || candidate.type === "tool_execution" || candidate.type === "action_text" || candidate.type === "artifact" || candidate.type === "preview" || candidate.type === "screenshot") {
      return true;
    }
  }

  return false;
}

function reorderForDisplay(blocks: ContentBlock[]): ContentBlock[] {
  const answers = blocks.filter((block) => block.type === "answer");
  if (answers.length === 0) return blocks;

  const firstAnswerIndex = blocks.findIndex((block) => block.type === "answer");
  if (firstAnswerIndex === -1) return blocks;

  const pinnedArtifacts = blocks.filter(
    (block, index) => block.type === "artifact" && index < firstAnswerIndex,
  );
  if (pinnedArtifacts.length === 0) return blocks;

  const withoutPinnedArtifacts = blocks.filter(
    (block, index) => !(block.type === "artifact" && index < firstAnswerIndex),
  );

  const lastAnswerIndex = withoutPinnedArtifacts.reduce((acc, block, index) => (
    block.type === "answer" ? index : acc
  ), -1);

  if (lastAnswerIndex === -1) return withoutPinnedArtifacts;

  return [
    ...withoutPinnedArtifacts.slice(0, lastAnswerIndex + 1),
    ...pinnedArtifacts,
    ...withoutPinnedArtifacts.slice(lastAnswerIndex + 1),
  ];
}

interface InterleavedBlockSequenceProps {
  blocks: ContentBlock[];
  showThinking: boolean;
  thinkingLevel?: ThinkingLevel;
  isStreaming?: boolean;
}

export function InterleavedBlockSequence({
  blocks,
  showThinking,
  thinkingLevel = "balanced",
  isStreaming = false,
}: InterleavedBlockSequenceProps) {
  const hasStandaloneToolBlocks = blocks.some((block) => block.type === "tool_execution");
  const groupedBlockIds = new Set<string>();
  for (const block of blocks) {
    if (block.type === "thinking" && block.groupId) {
      groupedBlockIds.add(block.id);
    }
  }

  const visibleBlocks = reorderForDisplay(
    blocks.filter((block) => {
      if (!showThinking || thinkingLevel === "minimal") {
        return !["thinking", "action_text", "tool_execution"].includes(block.type);
      }
      return true;
    }),
  );

  return (
    <>
      {visibleBlocks.map((block, index) => {
        if (block.type === "thinking" && groupedBlockIds.has(block.id)) {
          return null;
        }

        if (block.type === "subagent_group") {
          const childBlocks = visibleBlocks.filter(
            (candidate) => candidate.type === "thinking" && candidate.groupId === block.id,
          ) as ThinkingBlockData[];
          return (
            <SubagentGroup
              key={block.id}
              group={block as SubagentGroupBlockData}
              childBlocks={childBlocks}
              isStreaming={isStreaming}
              thinkingLevel={thinkingLevel}
            />
          );
        }

        if (block.type === "thinking") {
          const thinkingBlock = block as ThinkingBlockData;
          const continuation = isThinkingContinuation(visibleBlocks, index);
          return (
            <ThinkingBlock
              key={block.id}
              content={thinkingBlock.content}
              toolCalls={hasStandaloneToolBlocks ? [] : thinkingBlock.toolCalls}
              savedDuration={
                thinkingBlock.startTime && thinkingBlock.endTime
                  ? Math.round((thinkingBlock.endTime - thinkingBlock.startTime) / 1000)
                  : undefined
              }
              label={thinkingBlock.label}
              summary={thinkingBlock.summary || thinkingBlock.label}
              phase={thinkingBlock.phase}
              isStreaming={isStreaming && !thinkingBlock.endTime}
              autoExpand={isStreaming && !thinkingBlock.endTime}
              thinkingLevel={thinkingLevel}
              continuation={continuation}
            />
          );
        }

        if (block.type === "tool_execution") {
          return <ToolExecutionStrip key={block.id} block={block as ToolExecutionBlockData} />;
        }

        if (block.type === "action_text") {
          if (shouldHideActionBridge(visibleBlocks, index)) return null;
          return <ActionText key={block.id} content={block.content} node={block.node} />;
        }

        if (block.type === "screenshot") {
          return <ScreenshotBlock key={block.id} block={block as ScreenshotBlockData} />;
        }

        if (block.type === "preview") {
          return <PreviewGroup key={block.id} block={block as PreviewBlockData} />;
        }

        if (block.type === "artifact") {
          return <ArtifactCard key={block.id} artifact={(block as ArtifactBlockData).artifact} />;
        }

        if (block.type === "answer") {
          const isLastAnswer = !visibleBlocks.slice(index + 1).some((candidate) => candidate.type === "answer");
          return (
            <div key={block.id} className="assistant-response">
              <MarkdownRenderer content={block.content} />
              {isStreaming && isLastAnswer && (
                <span className="inline-block w-[2px] h-[1em] bg-[var(--accent-orange)] ml-0.5 align-middle animate-pulse rounded-sm" />
              )}
            </div>
          );
        }

        return null;
      })}
    </>
  );
}

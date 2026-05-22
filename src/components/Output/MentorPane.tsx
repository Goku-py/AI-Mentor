import { SparklesIcon } from "../Icons";
import type { Issue, AiMentorStatus } from "../../types";
import { aiMentorStatusCopy } from "../../types";

interface MentorPaneProps {
  isAnalyzing: boolean;
  mentorFeedback: string;
  aiMentorStatus: AiMentorStatus;
  errorMsg: string;
  issues: Issue[];
}

const renderMarkdown = (text: string | null | undefined) => {
  if (!text) return null;
  const parts = text.split(/(```[\s\S]*?```|`[^`]+`|\*\*[^*]+\*\*|\n\n)/g);
  return parts.map((part, i) => {
    if (part === "\n\n") return <br key={i} />;
    if (part.startsWith("```") && part.endsWith("```")) {
      const lines = part.slice(3, -3).split("\n");
      const code = lines.slice(1).join("\n") || lines[0];
      return <pre key={i}><code>{code}</code></pre>;
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return <code key={i}>{part.slice(1, -1)}</code>;
    }
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={i}>{part.slice(2, -2)}</strong>;
    }
    return <span key={i}>{part}</span>;
  });
};

export default function MentorPane({
  isAnalyzing,
  mentorFeedback,
  aiMentorStatus,
  errorMsg,
  issues,
}: MentorPaneProps) {
  return (
    <div className="mentor-pane">
      <div className="pane-header accent-text">
        <SparklesIcon /> AI Mentor Feedback
      </div>
      <div className="pane-content mentor-content" role="status" aria-live="polite">
        {isAnalyzing ? (
          <div className="placeholder-text">Analyzing code ...</div>
        ) : aiMentorStatus !== "ok" ? (
          <div className="placeholder-text" style={{ color: "var(--warning)" }}>
            <SparklesIcon />
            {aiMentorStatusCopy[aiMentorStatus]?.title || "AI Mentor is unavailable."}
            <br />
            {aiMentorStatusCopy[aiMentorStatus]?.body || "Check the server AI configuration and try again."}
          </div>
        ) : mentorFeedback && !(mentorFeedback === "LOOKS_GOOD" || mentorFeedback.startsWith("LOOKS_GOOD")) ? (
          <div>{renderMarkdown(mentorFeedback)}</div>
        ) : mentorFeedback && (mentorFeedback === "LOOKS_GOOD" || mentorFeedback.startsWith("LOOKS_GOOD")) ? (
          <div className="placeholder-text">
            <SparklesIcon />
            Your code ran successfully! No errors or logical flaws detected.
            <br />Keep up the great work.
          </div>
        ) : (errorMsg || issues.some((i) => i.severity === "error")) ? (
          <div className="placeholder-text">
            I will help explain any errors and how to fix them!
            <br /><br />
            (Note: Ensure your GEMINI_API_KEY is set in the server&apos;s .env file to enable AI Mentorship)
          </div>
        ) : (
          <div className="placeholder-text">
            <SparklesIcon />
            Your code executed cleanly. Make sure to include comments so I can verify your logic.
          </div>
        )}
      </div>
    </div>
  );
}

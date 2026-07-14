import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
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

export default function MentorPane({
  isAnalyzing,
  mentorFeedback,
  aiMentorStatus,
  errorMsg,
  issues,
}: MentorPaneProps) {
  const showLooksGood = mentorFeedback && (mentorFeedback === "LOOKS_GOOD" || mentorFeedback.startsWith("LOOKS_GOOD"));
  const showFeedback = mentorFeedback && !showLooksGood;

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
        ) : showFeedback ? (
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              code({ className, children }) {
                const isInline = !className;
                if (isInline) {
                  return <code>{children}</code>;
                }
                return (
                  <pre>
                    <code className={className}>{children}</code>
                  </pre>
                );
              },
            }}
          >
            {mentorFeedback}
          </ReactMarkdown>
        ) : showLooksGood ? (
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

import { PlayIcon, SunIcon, MoonIcon, LanguageIcon, UploadIcon, TrashIcon, FullscreenIcon, ShareIcon, CodeIcon } from "../Icons";
import LanguageSelector from "../Editor/LanguageSelector";
import UserBadge from "../Auth/UserBadge";
import type { User, Difficulty } from "../../types";
import { DIFFICULTIES } from "../../types";

interface ToolbarProps {
  code: string;
  language: string;
  fontSize: number;
  darkMode: boolean;
  isFullscreen: boolean;
  isAnalyzing: boolean;
  user: User | null;
  onRun: () => void;
  onCycleLanguage: () => void;
  onLanguageChange: (lang: string) => void;
  difficulty: Difficulty;
  onDifficultyChange: (difficulty: Difficulty) => void;
  onIncreaseFont: () => void;
  onDecreaseFont: () => void;
  onToggleDarkMode: () => void;
  onToggleFullscreen: () => void;
  onShare: () => void;
  onClearOutput: () => void;
  onFileUploadClick: () => void;
  onLoginClick: () => void;
  onLogout: () => void;
}

export default function Toolbar({
  code,
  language,
  darkMode,
  isFullscreen,
  isAnalyzing,
  user,
  onRun,
  onCycleLanguage,
  onLanguageChange,
  difficulty,
  onDifficultyChange,
  onIncreaseFont,
  onDecreaseFont,
  onToggleDarkMode,
  onToggleFullscreen,
  onShare,
  onClearOutput,
  onFileUploadClick,
  onLoginClick,
  onLogout,
}: ToolbarProps) {
  return (
    <header className="header">
      <div className="header-title">
        <CodeIcon />
        <span>AI Code Mentor</span>
      </div>
      <div className="controls">
        <button className="font-btn" title="Decrease font" onClick={onDecreaseFont} aria-label="Decrease font size">A−</button>
        <button className="font-btn" title="Increase font" onClick={onIncreaseFont} aria-label="Increase font size">A+</button>
        <button title="Toggle dark/light" onClick={onToggleDarkMode} aria-label="Toggle dark mode">{darkMode ? <SunIcon /> : <MoonIcon />}</button>
        <button title="Next language" onClick={onCycleLanguage} aria-label="Cycle to next language"><LanguageIcon /></button>
        <button
          title="Upload code file"
          aria-label="Upload code file"
          onClick={onFileUploadClick}
          onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onFileUploadClick(); } }}
        ><UploadIcon /></button>
        <LanguageSelector language={language} onLanguageChange={onLanguageChange} />
        <div className="difficulty-selector-wrapper">
          <select
            className="language-select difficulty-select"
            value={difficulty}
            onChange={(e: React.ChangeEvent<HTMLSelectElement>) => onDifficultyChange(e.target.value as Difficulty)}
            title="Select mentorship difficulty"
            aria-label="Select mentorship difficulty"
          >
            {DIFFICULTIES.map((level) => (
              <option key={level.id} value={level.id}>{level.name}</option>
            ))}
          </select>
        </div>
        <button
          className="run-btn"
          onClick={onRun}
          disabled={isAnalyzing || !code.trim()}
        >
          <PlayIcon />
          {isAnalyzing ? "Running..." : "Run"}
        </button>
        <button title="Clear output" onClick={onClearOutput} aria-label="Clear output"><TrashIcon /></button>
        <button title={isFullscreen ? "Exit fullscreen" : "Enter fullscreen"} onClick={onToggleFullscreen} aria-label={isFullscreen ? "Exit fullscreen" : "Enter fullscreen"}><FullscreenIcon exit={isFullscreen} /></button>
        <button title="Share" onClick={onShare} aria-label="Share code"><ShareIcon /></button>
        {user ? (
          <UserBadge user={user} onLogout={onLogout} />
        ) : (
          <button className="auth-login-btn" onClick={onLoginClick}>Sign in</button>
        )}
      </div>
    </header>
  );
}

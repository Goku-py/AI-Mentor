import { memo } from "react";
import { PlayIcon, SunIcon, MoonIcon, LanguageIcon, UploadIcon, TrashIcon, FullscreenIcon, CodeIcon } from "../Icons";
import LanguageSelector from "../Editor/LanguageSelector";
import UserBadge from "../Auth/UserBadge";
import type { User } from "../../types";

interface ToolbarProps {
  // Derived boolean, not the code string: passing the whole document would
  // invalidate React.memo on every keystroke.
  canRun: boolean;
  language: string;
  fontSize: number;
  darkMode: boolean;
  isFullscreen: boolean;
  isAnalyzing: boolean;
  user: User | null;
  onRun: () => void;
  onCycleLanguage: () => void;
  onLanguageChange: (lang: string) => void;
  onIncreaseFont: () => void;
  onDecreaseFont: () => void;
  onToggleDarkMode: () => void;
  onToggleFullscreen: () => void;
  onClearOutput: () => void;
  onFileUploadClick: () => void;
  onLoginClick: () => void;
  onLogout: () => void;
}

function Toolbar({
  canRun,
  language,
  darkMode,
  isFullscreen,
  isAnalyzing,
  user,
  onRun,
  onCycleLanguage,
  onLanguageChange,
  onIncreaseFont,
  onDecreaseFont,
  onToggleDarkMode,
  onToggleFullscreen,
  onClearOutput,
  onFileUploadClick,
  onLoginClick,
  onLogout,
}: ToolbarProps) {
  return (
    <header className="header" role="banner">
      <h1 className="header-title">
        <CodeIcon aria-hidden="true" />
        <span>AI Code Mentor</span>
      </h1>
      <nav className="controls" aria-label="Editor controls">
        <button className="font-btn" title="Decrease font" onClick={onDecreaseFont} aria-label="Decrease font size">A−</button>
        <button className="font-btn" title="Increase font" onClick={onIncreaseFont} aria-label="Increase font size">A+</button>
        <button title="Toggle dark/light" onClick={onToggleDarkMode} aria-label="Toggle dark mode">{darkMode ? <SunIcon /> : <MoonIcon />}</button>
        <button title="Next language" onClick={onCycleLanguage} aria-label="Cycle to next language"><LanguageIcon /></button>
        <button
          title="Upload code file"
          aria-label="Upload code file"
          onClick={onFileUploadClick}
        ><UploadIcon /></button>
        <LanguageSelector language={language} onLanguageChange={onLanguageChange} />
        <button
          className="run-btn"
          onClick={onRun}
          disabled={isAnalyzing || !canRun}
        >
          <PlayIcon />
          {isAnalyzing ? "Running..." : "Run"}
        </button>
        <button title="Clear output" onClick={onClearOutput} aria-label="Clear output"><TrashIcon /></button>
        <button title={isFullscreen ? "Exit fullscreen" : "Enter fullscreen"} onClick={onToggleFullscreen} aria-label={isFullscreen ? "Exit fullscreen" : "Enter fullscreen"}><FullscreenIcon exit={isFullscreen} /></button>
        {user ? (
          <UserBadge user={user} onLogout={onLogout} />
        ) : (
          <button className="auth-login-btn" onClick={onLoginClick} type="button">Sign in</button>
        )}
      </nav>
    </header>
  );
}

export default memo(Toolbar);

import { Group, Panel, Separator } from "react-resizable-panels";
import { useAuth } from "./hooks/useAuth";
import { useSettings } from "./hooks/useSettings";
import { useCode } from "./hooks/useCode";
import ErrorBoundary from "./components/ErrorBoundary";
import ToastContainer from "./components/Toast";
import Toolbar from "./components/Toolbar/Toolbar";
import EditorPane from "./components/Editor/EditorPane";
import OutputPane from "./components/Output/OutputPane";
import MentorPane from "./components/Output/MentorPane";
import AuthModal from "./components/Auth/AuthModal";

export default function App() {
  const auth = useAuth();
  const settings = useSettings();
  const code = useCode({
    accessToken: auth.accessToken,
    csrfToken: auth.csrfToken,
    tryRefreshToken: auth.tryRefreshToken,
    refreshCsrfToken: auth.refreshCsrfToken,
    onUnauthenticated: auth.handleUnauthenticated,
  });

  return (
    <ErrorBoundary>
      <ToastContainer />
      <div className="app-container">
        {auth.showAuthModal && (
          <AuthModal
            authTab={auth.authTab}
            authForm={auth.authForm}
            authError={auth.authError}
            authLoading={auth.authLoading}
            onClose={() => auth.setShowAuthModal(false)}
            onTabChange={(tab) => { auth.setAuthTab(tab); auth.setAuthError(""); }}
            onFormChange={auth.setAuthForm}
            onSubmit={auth.handleAuthSubmit}
          />
        )}

        <input
          type="file"
          accept=".py,.js,.java,.c,.cpp,.cc,.cxx"
          className="sr-only"
          tabIndex={-1}
          ref={code.fileInputRef}
          onChange={code.handleFileChange}
        />

        <Toolbar
          code={code.code}
          language={code.language}
          fontSize={settings.fontSize}
          darkMode={settings.darkMode}
          isFullscreen={settings.isFullscreen}
          isAnalyzing={code.isAnalyzing}
          user={auth.user}
          onRun={code.handleRun}
          onCycleLanguage={code.cycleLanguage}
          onLanguageChange={(lang) => code.handleLanguageChange(lang)}
          difficulty={code.difficulty}
          onDifficultyChange={code.setDifficulty}
          onIncreaseFont={settings.increaseFont}
          onDecreaseFont={settings.decreaseFont}
          onToggleDarkMode={settings.toggleDarkMode}
          onToggleFullscreen={settings.toggleFullscreen}
          onShare={code.handleShare}
          onClearOutput={code.clearOutput}
          onFileUploadClick={() => code.fileInputRef.current?.click()}
          onLoginClick={() => { auth.setShowAuthModal(true); auth.setAuthTab("login"); }}
          onLogout={auth.handleLogout}
        />

        <Group orientation="vertical" className="main-content">
          <Panel defaultSize={50} minSize={15}>
            <EditorPane
              code={code.code}
              language={code.language}
              fontSize={settings.fontSize}
              errorLine={code.errorLine}
              darkMode={settings.darkMode}
              onCodeChange={code.setCode}
              onRun={code.handleRun}
            />
          </Panel>
          <Separator className="resize-handle" />
          <Panel defaultSize={50} minSize={15}>
            <div className="side-pane">
              <OutputPane
                output={code.output}
                errorMsg={code.errorMsg}
                issues={code.issues}
                mismatchInfo={code.mismatchInfo}
                language={code.language}
                onLanguageChange={code.handleLanguageChange}
                onClearMismatch={code.clearMismatch}
              />
              <MentorPane
                isAnalyzing={code.isAnalyzing}
                mentorFeedback={code.mentorFeedback}
                aiMentorStatus={code.aiMentorStatus}
                errorMsg={code.errorMsg}
                issues={code.issues}
              />
            </div>
          </Panel>
        </Group>
      </div>
    </ErrorBoundary>
  );
}

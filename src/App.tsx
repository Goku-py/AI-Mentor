import { useAuth } from "./hooks/useAuth";
import { useSettings } from "./hooks/useSettings";
import { useCode } from "./hooks/useCode";
import ErrorBoundary from "./components/ErrorBoundary";
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
    onUnauthenticated: auth.handleUnauthenticated,
  });

  return (
    <ErrorBoundary>
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
          style={{ display: "none" }}
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

        <div className="main-content">
          <EditorPane
            code={code.code}
            language={code.language}
            fontSize={settings.fontSize}
            errorLine={code.errorLine}
            editorWrapperRef={code.editorWrapperRef}
            onCodeChange={code.setCode}
            onRun={code.handleRun}
          />
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
        </div>
      </div>
    </ErrorBoundary>
  );
}

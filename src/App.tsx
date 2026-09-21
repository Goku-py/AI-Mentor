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

function NotFound() {
  return (
    <main className="not-found" role="main" aria-labelledby="nf-title">
      <div className="not-found-code" aria-hidden="true">404</div>
      <h1 id="nf-title" className="not-found-title">Page not found</h1>
      <p className="not-found-desc">
        The page you’re looking for doesn’t exist. Return to the editor and keep building.
      </p>
      <a href="/" className="not-found-link">Back to editor</a>
    </main>
  );
}

export default function App() {
  const auth = useAuth();
  const settings = useSettings();
  const code = useCode({
    accessToken: auth.accessToken,
    csrfToken: auth.csrfToken,
    tryRefreshToken: auth.tryRefreshToken,
    onUnauthenticated: auth.handleUnauthenticated,
  });

  const isNotFound = typeof window !== "undefined" && window.location.pathname !== "/" && window.location.pathname !== "/index.html";
  if (isNotFound) {
    return (
      <ErrorBoundary>
        <a className="skip-link" href="#main-content">Skip to content</a>
        <div className="app-container">
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
          <NotFound />
        </div>
      </ErrorBoundary>
    );
  }

  return (
    <ErrorBoundary>
      <a className="skip-link" href="#main-content">Skip to content</a>
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
          aria-hidden="true"
          aria-label="Upload code file"
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

        <main id="main-content" className="main-content" role="main" aria-label="Code editor and output">
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
        </main>
      </div>
    </ErrorBoundary>
  );
}

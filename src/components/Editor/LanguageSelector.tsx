import { SUPPORTED_LANGUAGES } from "../../types";

interface LanguageSelectorProps {
  language: string;
  onLanguageChange: (lang: string) => void;
}

export default function LanguageSelector({ language, onLanguageChange }: LanguageSelectorProps) {
  return (
    <div className="language-selector-wrapper">
      <select
        className="language-select"
        value={language}
        onChange={(e: React.ChangeEvent<HTMLSelectElement>) => onLanguageChange(e.target.value)}
        title="Select programming language"
        aria-label="Select programming language"
      >
        {SUPPORTED_LANGUAGES.map((lang) => (
          <option key={lang.id} value={lang.id}>{lang.name}</option>
        ))}
      </select>
    </div>
  );
}

document.addEventListener("DOMContentLoaded", () => {
    const codeInput = document.getElementById("code-input");
    const languageSelect = document.getElementById("language-select");
    const analyzeButton = document.getElementById("analyze-btn");
    const resultsContainer = document.getElementById("results");

    if (!codeInput || !languageSelect || !analyzeButton || !resultsContainer) {
        // If the DOM is not in the expected shape, fail silently on the frontend.
        return;
    }

    const renderMessage = (text, type = "info") => {
        resultsContainer.innerHTML = "";
        const p = document.createElement("p");
        p.textContent = text;
        p.className = `results-message results-message--${type}`;
        resultsContainer.appendChild(p);
    };

    const renderResult = (data) => {
        resultsContainer.innerHTML = "";

        const header = document.createElement("div");
        header.className = "results-summary";

        const summaryText = document.createElement("p");
        const issueCount = data?.summary?.issue_count ?? 0;
        const lineCount = data?.summary?.line_count ?? 0;
        const lang = data?.language || languageSelect.value || "python";
        summaryText.textContent = `Language: ${lang} · Analyzed ${lineCount} line(s). Found ${issueCount} issue(s).`;

        header.appendChild(summaryText);
        resultsContainer.appendChild(header);

        // Issues list
        if (!Array.isArray(data.issues) || data.issues.length === 0) {
            const ok = document.createElement("p");
            ok.className = "results-ok";
            ok.textContent = "No issues detected by the current rule set.";
            resultsContainer.appendChild(ok);
        } else {
            const list = document.createElement("ul");
            list.className = "results-list";

            data.issues.forEach((issue) => {
                const item = document.createElement("li");
                item.className = `results-item results-item--${issue.severity || "info"}`;

                const title = document.createElement("div");
                title.className = "results-item-title";
                const line = issue.line != null ? `Line ${issue.line}: ` : "";
                title.textContent = `${line}[${issue.severity?.toUpperCase() || "INFO"}] ${issue.code || ""}`.trim();

                const message = document.createElement("div");
                message.className = "results-item-message";
                message.textContent = issue.message || "";

                item.appendChild(title);
                item.appendChild(message);
                list.appendChild(item);
            });

            resultsContainer.appendChild(list);
        }

        // Execution details (program output, runtime errors, tool availability)
        const exec = data.execution || {};
        const hasStdout = typeof exec.stdout === "string" && exec.stdout.trim().length > 0;
        const hasStderr = typeof exec.stderr === "string" && exec.stderr.trim().length > 0;
        const hasError = !!exec.error;
        const hasTimeout = !!exec.timed_out;
        const toolMissing = !!exec.tool_missing;

        if (hasStdout || hasStderr || hasError || hasTimeout || toolMissing) {
            const execBlock = document.createElement("div");
            execBlock.className = "execution-block";

            const execTitle = document.createElement("h3");
            execTitle.className = "execution-title";
            execTitle.textContent = "Program Output & Error Details";
            execBlock.appendChild(execTitle);

            if (hasStdout) {
                const outSection = document.createElement("section");
                outSection.className = "execution-section";

                const outLabel = document.createElement("div");
                outLabel.className = "execution-label";
                outLabel.textContent = "Standard Output";

                const outPre = document.createElement("pre");
                outPre.className = "execution-pre";
                outPre.textContent = exec.stdout;

                outSection.appendChild(outLabel);
                outSection.appendChild(outPre);
                execBlock.appendChild(outSection);
            }

            if (toolMissing) {
                const toolMsg = document.createElement("p");
                toolMsg.className = "results-message results-message--warning";
                toolMsg.textContent =
                    exec?.error?.message ||
                    "Required compiler or runtime is not available on the server for this language.";
                execBlock.appendChild(toolMsg);
            }

            if (hasTimeout) {
                const timeoutMsg = document.createElement("p");
                timeoutMsg.className = "results-message results-message--warning";
                timeoutMsg.textContent =
                    exec?.error?.message ||
                    "Program execution took too long and was stopped (possible infinite loop or heavy computation).";
                execBlock.appendChild(timeoutMsg);
            }

            if (hasError) {
                const errSection = document.createElement("section");
                errSection.className = "execution-section";

                const errLabel = document.createElement("div");
                errLabel.className = "execution-label";
                errLabel.textContent = "Error Explanation";

                const errMain = document.createElement("p");
                errMain.className = "execution-error-main";
                const typeText = exec.error.type ? `${exec.error.type}: ` : "";
                errMain.textContent = `${typeText}${exec.error.message || ""}`.trim();

                const errDetails = document.createElement("p");
                errDetails.className = "execution-error-details";
                const lineInfo =
                    exec.error.line != null ? `Likely problem near line ${exec.error.line}. ` : "";
                errDetails.textContent = `${lineInfo}${exec.error.explanation || ""}`.trim();

                errSection.appendChild(errLabel);
                errSection.appendChild(errMain);
                errSection.appendChild(errDetails);

                if (Array.isArray(exec.error.suggestions) && exec.error.suggestions.length > 0) {
                    const sugLabel = document.createElement("div");
                    sugLabel.className = "execution-suggestions-label";
                    sugLabel.textContent = "Suggestions:";

                    const sugList = document.createElement("ul");
                    sugList.className = "execution-suggestions-list";

                    exec.error.suggestions.forEach((sug) => {
                        const li = document.createElement("li");
                        li.textContent = sug;
                        sugList.appendChild(li);
                    });

                    errSection.appendChild(sugLabel);
                    errSection.appendChild(sugList);
                }

                if (hasStderr) {
                    const rawErrLabel = document.createElement("div");
                    rawErrLabel.className = "execution-label";
                    rawErrLabel.textContent = "Raw Error Output";

                    const rawErrPre = document.createElement("pre");
                    rawErrPre.className = "execution-pre execution-pre--error";
                    rawErrPre.textContent = exec.stderr;

                    errSection.appendChild(rawErrLabel);
                    errSection.appendChild(rawErrPre);
                }

                execBlock.appendChild(errSection);
            } else if (hasStderr) {
                const rawSection = document.createElement("section");
                rawSection.className = "execution-section";

                const rawLabel = document.createElement("div");
                rawLabel.className = "execution-label";
                rawLabel.textContent = "Raw Error Output";

                const rawPre = document.createElement("pre");
                rawPre.className = "execution-pre execution-pre--error";
                rawPre.textContent = exec.stderr;

                rawSection.appendChild(rawLabel);
                rawSection.appendChild(rawPre);
                execBlock.appendChild(rawSection);
            }

            resultsContainer.appendChild(execBlock);
        }
    };

    const analyze = async () => {
        const rawCode = codeInput.value || "";
        const language = languageSelect.value || "python";
        const trimmed = rawCode.trim();

        if (!trimmed) {
            renderMessage("Please paste some code before running the analysis.", "warning");
            codeInput.focus();
            return;
        }

        analyzeButton.disabled = true;
        analyzeButton.textContent = "Analyzing...";

        try {
            const response = await fetch("/analyze", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    code: rawCode,
                    language,
                }),
            });

            const data = await response.json().catch(() => ({}));

            if (!response.ok || data.ok === false) {
                const errorText =
                    data?.error ||
                    `Analysis request failed with status ${response.status} (${response.statusText}).`;
                renderMessage(errorText, "error");
                return;
            }

            renderResult(data);
        } catch (err) {
            renderMessage("Network error while contacting the analyzer. Please try again.", "error");
        } finally {
            analyzeButton.disabled = false;
            analyzeButton.textContent = "Analyze Code";
        }
    };

    analyzeButton.addEventListener("click", analyze);

    codeInput.addEventListener("keydown", (event) => {
        if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
            event.preventDefault();
            analyze();
        }
    });
});

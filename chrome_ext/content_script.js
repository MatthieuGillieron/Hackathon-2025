// Email content script for Chrome extension
// Adds functionality to extract email information and integrate with calendar

(() => {
    console.log("Content script loaded");

    // Constants
    const CONFIG = {
        buttonId: "event_api_call",
        buttonHtml: `
      <style>
        .ai-btn {
          padding: 8px;
          border: 2px solid transparent;
          background: #0098ff;
          color: white;
          border-radius: 35px;
          cursor: pointer;
          font-weight: 500;
          font-size: 13px;
          transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
          position: relative;
          overflow: hidden;
          box-shadow: 0 2px 8px rgba(0, 152, 255, 0.3);
          display: flex;
          align-items: center;
          gap: 6px;
          white-space: nowrap;
          margin-left: 8px;
        }
        .ai-btn .material-icons {
          font-size: 18px;
        }
        .ai-btn .btn-text {
          display: none;
        }
        .ai-btn:hover {
          transform: translateY(-2px);
          box-shadow: 0 4px 15px rgba(0, 152, 255, 0.4);
          background: #0080d9;
          padding: 8px 16px;
        }
        .ai-btn:hover .btn-text {
          display: inline;
        }
      </style>
      <button type="button" id="event_api_call" class="ai-btn">
        <span class="material-icons">event_available</span>
        <span class="btn-text">AI événement</span>
      </button>
      <button type="button" id="summary_api_call" class="ai-btn">
        <span class="material-icons">summarize</span>
        <span class="btn-text">AI résumé</span>
      </button>
      <button type="button" id="reply_api_call" class="ai-btn">
        <span class="material-icons">reply</span>
        <span class="btn-text">AI réponse</span>
      </button>
    `,
        classifyButtonHtml: `
          <button type="button" id="classify_api_call" class="mat-focus-indicator mailFooter-button mat-raised-button mat-button-base ng-star-inserted" style="margin-left: 0; border: 2px solid #D81B60; border-radius: 4px; background-color: #333333; color: white; width: 100%; height: 40px; display: flex; align-items: center; justify-content: center; position: relative;">
        <span class="mat-button-wrapper" style="display: flex; align-items: center; justify-content: center; width: 100%; height: 100%; position: absolute; top: 0; left: 0;">
          <div style="display: flex; align-items: center; justify-content: center; gap: 8px;">
            <span class="material-icons" style="font-size: 18px;">auto_awesome</span>
            <span style="font-size: 14px; font-weight: 500;">AI rangement</span>
          </div>
        </span>
        <span class="mat-ripple mat-button-ripple"></span>
        <span class="mat-button-focus-overlay"></span>
      </button>
    `,
        filterDivId: "mail_filter_buttons",
        filterDivHtml: `
      <style>
        @import url('https://fonts.googleapis.com/icon?family=Material+Icons');
        #mail_filter_buttons {
          padding: 12px 20px;
          background: transparent;
          display: flex;
          gap: 12px;
          align-items: center;
        }
        .filter-btn {
          padding: 8px;
          border: 2px solid transparent;
          background: #F2357A;
          color: white;
          border-radius: 35px;
          cursor: pointer;
          font-weight: 500;
          font-size: 13px;
          transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
          position: relative;
          overflow: hidden;
          box-shadow: 0 2px 8px rgba(242, 53, 122, 0.3);
          display: flex;
          align-items: center;
          gap: 6px;
          white-space: nowrap;
        }
        .filter-btn .material-icons {
          font-size: 18px;
        }
        .filter-btn .btn-text {
          display: none;
        }
        .filter-btn.active {
          padding: 8px 16px;
        }
        .filter-btn.active .btn-text {
          display: inline;
        }
        .filter-btn:hover {
          transform: translateY(-2px);
          box-shadow: 0 4px 15px rgba(242, 53, 122, 0.4);
          background: #e02a6b;
        }
        .filter-btn.active {
          background: #F2357A;
          border-color: white;
          transform: translateY(-1px);
          box-shadow: 0 4px 15px rgba(242, 53, 122, 0.4);
        }
        .filter-btn::before {
          content: '';
          position: absolute;
          top: 0;
          left: -100%;
          width: 100%;
          height: 100%;
          background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
          transition: left 0.5s;
        }
        .filter-btn:hover::before {
          left: 100%;
        }
      </style>
      <div id="mail_filter_buttons">
        <button class="filter-btn" data-filter="principale">
          <span class="material-icons">inbox</span>
          <span class="btn-text">Principale</span>
        </button>
        <button class="filter-btn" data-filter="events">
          <span class="material-icons">event</span>
          <span class="btn-text">Events</span>
        </button>
        <button class="filter-btn" data-filter="notifications">
          <span class="material-icons">notifications</span>
          <span class="btn-text">Notifications</span>
        </button>
        <button class="filter-btn" data-filter="publicites">
          <span class="material-icons">campaign</span>
          <span class="btn-text">Publicités</span>
        </button>
        <button class="filter-btn active" data-filter="tous">
          <span class="material-icons">mail</span>
          <span class="btn-text">Tous les mails</span>
        </button>
      </div>
    `,
        calendarBaseUrl: "https://calendar.infomaniak.com/create",
        mailPattern: /mail-(\d+)@([a-zA-Z0-9-]+)/g,
        targetSelector: "div.mailContent-open-footer.ng-star-inserted",
        messageItemSelector: "div.message-item"
    };

    const parseDateTime = (dateStr, timeStr) => {
        try {
            const [y, m, d] = dateStr.split("-").map(Number);
            const [hh, mm] = timeStr.split(":").map(Number);
            if (Number.isFinite(y) && Number.isFinite(m) && Number.isFinite(d) && Number.isFinite(hh) && Number.isFinite(mm)) {
                return new Date(y, m - 1, d, hh, mm);
            }
        } catch {
            /* noop */
        }
        return null;
    };

    const formatAsCalendarDate = (date) => date.toISOString().replace(/[-:]|\.\d{3}/g, "");

    // Storage for collected frame data (reserved for future multi-frame aggregation)
    const frameDataCollection = new Map();

    // ---- Chrome API helpers (Promise-based) ----
    const storageGet = (keys) => new Promise((resolve) => chrome.storage.local.get(keys, resolve));

    const runtimeSendMessage = (message) => new Promise((resolve) => chrome.runtime.sendMessage(message, resolve));

    // ---- DOM helpers ----
    const qsAll = (sel, root = document) => Array.from(root.querySelectorAll(sel));

    // ---- Content extraction ----
    const getMessageItemContent = () => qsAll(CONFIG.messageItemSelector)
        .map((el) => el.className)
        .join(" ");

    // ---- Pattern parsing ----
    const extractEmailThreadInfo = (content) => {
        const formattedEmails = [];
        const folderThreads = [];
        let match;

        while ((match = CONFIG.mailPattern.exec(content)) !== null) {
            const [, threadId, folderId] = match;
            formattedEmails.push(`${threadId}@${folderId}`);
            folderThreads.push({ threadId, folderId });
        }

        return { formattedEmails, folderThreads };
    };

    // ============================================================================================
    // Suggestion
    // ============================================================================================

    const callApi = async (content) => {
        const { formattedEmails, folderThreads } = extractEmailThreadInfo(content);
        if (folderThreads.length === 0) return;

        const { mailboxIds = [] } = await storageGet({ mailboxIds: [] });
        if (mailboxIds.length === 0) return;

        const mailboxId = mailboxIds[0];
        const lastThread = folderThreads[folderThreads.length - 1];

        const response = await runtimeSendMessage({
            action: "callApi", payload: {
                mailboxId, folderId: lastThread.folderId, threadId: lastThread.threadId, context: formattedEmails,
            },
        });

        handleApiResponse(response);
    };

    const handleApiResponse = (response) => {
        if (!response || response.error) {
            console.error("API call failed:", response?.error ?? "Unknown error");
            return;
        }

        const params = new URLSearchParams({ ctz: "Europe/Zurich" });

        if (response.title) params.set("text", response.title);

        const emailsText = Array.isArray(response.emails) && response.emails.length ? `Participants:\n${response.emails.join("\n")}` : "";

        const mergedDescription = [response.description, emailsText]
            .filter(Boolean)
            .join("\n\n");

        if (mergedDescription) params.set("details", mergedDescription);

        if (response.date && response.start_time) {
            const start = parseDateTime(response.date, response.start_time);
            if (start) {
                const end = new Date(start);
                end.setMinutes(end.getMinutes() + (Number(response.duration) || 60));
                params.set("dates", `${formatAsCalendarDate(start)}/${formatAsCalendarDate(end)}`);
            }
        }

        const url = `${CONFIG.calendarBaseUrl}?${params.toString()}`;
        console.log("Opening calendar URL:", url);
        window.open(url, "_blank", "noopener,noreferrer");
    };

    // ============================================================================================
    // Summary
    // ============================================================================================

    const callSummaryApi = async (content) => {
        const { formattedEmails, folderThreads } = extractEmailThreadInfo(content);
        if (folderThreads.length === 0) return;

        const { mailboxIds = [] } = await storageGet({ mailboxIds: [] });
        if (mailboxIds.length === 0) return;

        const mailboxId = mailboxIds[0];
        const lastThread = folderThreads[folderThreads.length - 1];

        const response = await runtimeSendMessage({
            action: "callSummaryApi", payload: {
                mailboxId, folderId: lastThread.folderId, threadId: lastThread.threadId, context: formattedEmails,
            },
        });

        handleSummaryResponse(response);
    };

    const handleSummaryResponse = (response) => {
        if (!response || response.error) {
            console.error("Summary API call failed:", response?.error ?? "Unknown error");
            return;
        }
        // Create and show summary modal
        showSummaryModal(response);
    };

    const showSummaryModal = (summaryData) => {
        // Remove existing modal if any
        const existingModal = document.getElementById('email-summary-modal');
        if (existingModal) existingModal.remove();

        const modal = document.createElement('div');
        modal.id = 'email-summary-modal';
        modal.innerHTML = `
            <div style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 10000; display: flex; align-items: center; justify-content: center;">
                <div style="background: white; padding: 24px; border-radius: 12px; max-width: 600px; max-height: 80vh; overflow-y: auto; box-shadow: 0 10px 30px rgba(0,0,0,0.3);">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                        <h2 style="margin: 0; color: #333; font-size: 20px;">📧 Résumé de l'email</h2>
                        <button id="close-summary" style="background: none; border: none; font-size: 24px; cursor: pointer; color: #666;">&times;</button>
                    </div>
                    <div style="margin-bottom: 16px;">
                        <h3 style="color: #6c5ce7; margin-bottom: 8px;">Résumé</h3>
                        <p style="line-height: 1.6; color: #555;">${summaryData.summary}</p>
                    </div>
                    <div style="margin-bottom: 16px;">
                        <h3 style="color: #6c5ce7; margin-bottom: 8px;">Points clés</h3>
                        <ul style="margin: 0; padding-left: 20px;">
                            ${summaryData.key_points.map(point => `<li style="margin-bottom: 4px; color: #555;">${point}</li>`).join('')}
                        </ul>
                    </div>
                    <div>
                        <h3 style="color: #6c5ce7; margin-bottom: 8px;">Participants</h3>
                        <div style="display: flex; flex-wrap: wrap; gap: 8px;">
                            ${summaryData.participants.map(participant => `<span style="background: #f0f0f0; padding: 4px 8px; border-radius: 16px; font-size: 14px; color: #333;">${participant}</span>`).join('')}
                        </div>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        // Close modal handlers
        modal.querySelector('#close-summary').addEventListener('click', () => modal.remove());
        modal.addEventListener('click', (e) => {
            if (e.target === modal) modal.remove();
        });
    };

    // ============================================================================================
    // Reply
    // ============================================================================================

    const callReplyApi = async (content) => {
        const { formattedEmails, folderThreads } = extractEmailThreadInfo(content);
        if (folderThreads.length === 0) return;

        const { mailboxIds = [] } = await storageGet({ mailboxIds: [] });
        if (mailboxIds.length === 0) return;

        const mailboxId = mailboxIds[0];
        const lastThread = folderThreads[folderThreads.length - 1];

        const response = await runtimeSendMessage({
            action: "callReplyApi", payload: {
                mailboxId, folderId: lastThread.folderId, threadId: lastThread.threadId, context: formattedEmails,
            },
        });

        handleReplyResponse(response);
    };

    // ---- Reply response handling ----
    const handleReplyResponse = (response) => {
        if (!response || response.error) {
            console.error("Reply API call failed:", response?.error ?? "Unknown error");
            return;
        }

        // Show reply modal with generated content
        showReplyModal(response);
    };

    const showReplyModal = (replyData) => {
        // Remove existing modal if any
        const existingModal = document.getElementById('email-reply-modal');
        if (existingModal) existingModal.remove();

        const modal = document.createElement('div');
        modal.id = 'email-reply-modal';
        modal.innerHTML = `
            <div style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 10000; display: flex; align-items: center; justify-content: center;">
                <div style="background: white; padding: 24px; border-radius: 12px; max-width: 700px; width: 90%; max-height: 80vh; overflow-y: auto; box-shadow: 0 10px 30px rgba(0,0,0,0.3);">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                        <h2 style="margin: 0; color: #333; font-size: 20px;">✉️ Réponse générée par l'IA</h2>
                        <button id="close-reply" style="background: none; border: none; font-size: 24px; cursor: pointer; color: #666;">&times;</button>
                    </div>
                    <div style="margin-bottom: 16px;">
                        <label style="display: block; margin-bottom: 8px; font-weight: 500; color: #333;">Sujet:</label>
                        <input type="text" id="reply-subject" value="${replyData.subject}" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px;">
                    </div>
                    <div style="margin-bottom: 20px;">
                        <label style="display: block; margin-bottom: 8px; font-weight: 500; color: #333;">Message:</label>
                        <textarea id="reply-body" rows="12" style="width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; font-family: inherit; resize: vertical;">${replyData.body}</textarea>
                    </div>
                    <div style="margin-bottom: 16px;">
                        <small style="color: #666; font-style: italic;">Ton: ${replyData.tone}</small>
                    </div>
                    <div style="display: flex; gap: 12px; justify-content: flex-end;">
                        <button id="copy-reply" style="padding: 10px 20px; background: #6c5ce7; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 14px;">Copier</button>
                        <button id="close-reply-btn" style="padding: 10px 20px; background: #ddd; color: #333; border: none; border-radius: 6px; cursor: pointer; font-size: 14px;">Fermer</button>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        // Close modal handlers
        const closeModal = () => modal.remove();
        modal.querySelector('#close-reply').addEventListener('click', closeModal);
        modal.querySelector('#close-reply-btn').addEventListener('click', closeModal);
        modal.addEventListener('click', (e) => {
            if (e.target === modal) closeModal();
        });

        // Copy functionality
        modal.querySelector('#copy-reply').addEventListener('click', () => {
            const subject = modal.querySelector('#reply-subject').value;
            const body = modal.querySelector('#reply-body').value;
            const fullText = `Sujet: ${subject}\n\n${body}`;

            navigator.clipboard.writeText(fullText).then(() => {
                const btn = modal.querySelector('#copy-reply');
                const originalText = btn.textContent;
                btn.textContent = 'Copié !';
                btn.style.background = '#00b894';
                setTimeout(() => {
                    btn.textContent = originalText;
                    btn.style.background = '#6c5ce7';
                }, 2000);
            }).catch(err => {
                console.error('Failed to copy:', err);
            });
        });
    };

    // ============================================================================================
    // Classifier
    // ============================================================================================


    const callClassifierApi = async (content) => {
        const { formattedEmails, folderThreads } = extractEmailThreadInfo(content);
        if (folderThreads.length === 0) return;

        const { mailboxIds = [] } = await storageGet({ mailboxIds: [] });
        if (mailboxIds.length === 0) return;

        const mailboxId = mailboxIds[0];
        const lastThread = folderThreads[folderThreads.length - 1];

        const response = await runtimeSendMessage({
            action: "callClassifierApi", payload: {
                mailboxId, folderId: lastThread.folderId, threadId: lastThread.threadId, context: formattedEmails,
            },
        });

        handleClassifierResponse(response);
    }

    const handleClassifierResponse = (response) => {

    }


    // ---- Filter div insertion ----
    const insertFilterDiv = () => {
        const mailToolbar = document.querySelector('.mail-toolbar');
        const mailListBody = document.querySelector('.mail-list__body.mail-scroll');


        if (!mailToolbar || !mailListBody || document.querySelector(`#${CONFIG.filterDivId}`))
            return;

        mailListBody.insertAdjacentHTML('beforebegin', CONFIG.filterDivHtml);

        // Add click handlers for filter buttons
        const filterButtons = document.querySelectorAll('.filter-btn');
        filterButtons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                // Remove active class from all buttons
                filterButtons.forEach(b => b.classList.remove('active'));
                // Add active class to clicked button
                e.target.classList.add('active');

                const filter = e.target.dataset.filter;
                console.log('Filter selected:', filter);
                // TODO: Implement actual filtering logic
            });
        });
    };

    // ---- Button insertion ----
    const insertEmailButtons = (targetDiv) => {
        if (!targetDiv || targetDiv.querySelector(`#${CONFIG.buttonId}`)) return;

        targetDiv.insertAdjacentHTML("beforeend", CONFIG.buttonHtml);

        const btn = targetDiv.querySelector(`#${CONFIG.buttonId}`);
        if (btn) {
            btn.addEventListener("click", () => {
                const content = getMessageItemContent();
                callApi(content).catch((err) => console.error("Failed to call API:", err));
            });
        }

        const summaryBtn = targetDiv.querySelector('#summary_api_call');
        if (summaryBtn) {
            summaryBtn.addEventListener("click", () => {
                const content = getMessageItemContent();
                callSummaryApi(content).catch((err) => console.error("Failed to call Summary API:", err));
            });
        }

        const replyBtn = targetDiv.querySelector('#reply_api_call');
        if (replyBtn) {
            replyBtn.addEventListener("click", () => {
                const content = getMessageItemContent();
                callReplyApi(content).catch((err) => console.error("Failed to call Reply API:", err));
            });
        }
    };

    const insertClassifyButton = () => {
        // Add Material Icons link if not already present
        if (!document.querySelector('link[href*="material-icons"]')) {
            const link = document.createElement('link');
            link.href = 'https://fonts.googleapis.com/icon?family=Material+Icons';
            link.rel = 'stylesheet';
            document.head.appendChild(link);
        }
        const menuTitleDiv = document.querySelector('.menu-title.desktop');
        if (menuTitleDiv && !document.querySelector('.menu-button-classify')) {
            const classifyDiv = document.createElement('div');
            classifyDiv.className = 'menu-button-classify';
            classifyDiv.style.margin = '12px 0';
            classifyDiv.style.padding = '0 8px';
            classifyDiv.innerHTML = CONFIG.classifyButtonHtml;
            menuTitleDiv.insertAdjacentElement('afterend', classifyDiv);
            const classifyBtn = classifyDiv.querySelector('#classify_api_call');
            if (classifyBtn) {
                classifyBtn.addEventListener('click', () => {
                    console.log('click')
                    const content = getMessageItemContent();
                    callClassifierApi(content).catch((err) => console.error("Failed to call API:", err));
                });
            }
        }
    };

    // Observe for target container appearance and insert the button and filter div
    const observer = new MutationObserver(() => {
        const targetDiv = document.querySelector(CONFIG.targetSelector);
        if (targetDiv) {
            insertEmailButtons(targetDiv);
        }

        // Insert filter div between mail-toolbar and mail-list_body
        insertFilterDiv();
        insertClassifyButton();
    });

    // Start observing when DOM is ready
    const startObserving = () => {
        try {
            observer.observe(document.body, {
                childList: true, subtree: true,
            });

            // Attempt immediate insertion if already present
            const targetDiv = document.querySelector(CONFIG.targetSelector);
            if (targetDiv) insertEmailButtons(targetDiv);

            // Attempt immediate insertion of filter div
            insertFilterDiv();
            insertClassifyButton();
        } catch (e) {
            console.warn("MutationObserver setup failed:", e);
        }
    };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", startObserving, { once: true });
    } else {
        startObserving();
    }

    // ---- Message handling (for popup or other scripts) ----
    chrome.runtime.onMessage.addListener((request, _sender, sendResponse) => {
        if (request?.action === "extractMessageItems") {
            try {
                const data = getMessageItemContent();
                // Optional: store per-frame data if needed later
                frameDataCollection.set(performance.now(), data);
                sendResponse({ success: true, data });
            } catch (error) {
                console.error("Extraction error:", error);
                sendResponse({ success: false, error: String(error) });
            }
            return true; // async-safe
        }

        return false; // not handled
    });

})();
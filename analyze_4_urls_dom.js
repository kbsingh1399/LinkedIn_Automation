const fs = require('fs');
const path = require('path');

const REPORT_PATH = "C:\\Users\\SIGMA\\.gemini\\antigravity-ide\\brain\\728c3d79-fe7b-4a11-9cd2-0486c8fc9c68\\four_urls_dom_analysis.json";

const TARGET_URLS = [
    "https://www.linkedin.com/feed/",
    "https://www.linkedin.com/notifications/",
    "https://www.linkedin.com/messaging/",
    "https://gemini.google.com/app"
];

async function main() {
    console.log("===========================================================================");
    console.log(" 🔬 JS-BASED CDP DOM ANALYSIS AGENT (NODE.JS PROTOCOL)");
    console.log("===========================================================================");

    try {
        const verRes = await fetch("http://127.0.0.1:9222/json/version");
        const versionInfo = await verRes.json();
        const wsUrl = versionInfo.webSocketDebuggerUrl;
        console.log(`🔗 Connected to Chrome CDP WebSocket: ${wsUrl}`);

        const listRes = await fetch("http://127.0.0.1:9222/json/list");
        const targets = await listRes.json();
        const pageTargets = targets.filter(t => t.type === 'page');

        if (pageTargets.length === 0) {
            console.log("⚠️ No active page targets found.");
            process.exit(1);
        }

        const primaryTarget = pageTargets[0];
        console.log(`📌 Primary Target Tab ID: ${primaryTarget.id} (${primaryTarget.title})`);

        const ws = new WebSocket(wsUrl);
        let sessionId = null;

        ws.onopen = () => {
            ws.send(JSON.stringify({ id: 1, method: "Target.activateTarget", params: { targetId: primaryTarget.id } }));
        };

        const analysisResults = [];
        let urlIndex = 0;

        ws.onmessage = async (event) => {
            const msg = JSON.parse(event.data);

            if (msg.id === 1) {
                ws.send(JSON.stringify({
                    id: 2,
                    method: "Target.attachToTarget",
                    params: { targetId: primaryTarget.id, flatten: true }
                }));
            } else if (msg.id === 2) {
                sessionId = msg.result.sessionId;
                processNextUrl();
            } else if (msg.id === 10) {
                // Wait 4s for DOM rendering
                setTimeout(() => {
                    executeDomQuery();
                }, 4000);
            } else if (msg.id === 20) {
                const domData = msg.result.result ? msg.result.result.value : {};
                const currentUrl = TARGET_URLS[urlIndex];
                
                console.log(`\n───────────────────────────────────────────────────────────────────────────`);
                console.log(`📊 DOM ANALYSIS COMPLETE FOR: ${currentUrl}`);
                console.log(`📄 Page Title: ${domData.title || ''}`);
                console.log(`🔍 Structural Metrics Found:`);
                for (const [key, val] of Object.entries(domData.metrics || {})) {
                    console.log(`   • ${key.padEnd(24)}: ${val.count} found (aria='${val.sample_aria || ''}')`);
                }

                analysisResults.push({
                    url: currentUrl,
                    actual_url: domData.url,
                    title: domData.title,
                    metrics: domData.metrics
                });

                urlIndex++;
                if (urlIndex < TARGET_URLS.length) {
                    processNextUrl();
                } else {
                    saveReportAndExit();
                }
            }
        };

        function processNextUrl() {
            const targetUrl = TARGET_URLS[urlIndex];
            console.log(`\n📌 Navigating to [${urlIndex + 1}/${TARGET_URLS.length}]: ${targetUrl} ...`);
            ws.send(JSON.stringify({
                id: 10,
                sessionId: sessionId,
                method: "Page.navigate",
                params: { url: targetUrl }
            }));
        }

        function executeDomQuery() {
            const domQueryScript = `
                (function() {
                    const getCount = (sel) => document.querySelectorAll(sel).length;
                    const getSample = (sel) => {
                        const el = document.querySelector(sel);
                        return el ? { tag: el.tagName, aria: el.getAttribute('aria-label') || '', placeholder: el.getAttribute('placeholder') || '' } : null;
                    };

                    const href = window.location.href;
                    let metrics = {};

                    if (href.includes("linkedin.com/feed")) {
                        metrics = {
                            Comment_Buttons: { count: getCount("button[aria-label*='Comment']"), sample_aria: getSample("button[aria-label*='Comment']")?.aria },
                            Repost_Buttons: { count: getCount("button[aria-label*='Repost']"), sample_aria: getSample("button[aria-label*='Repost']")?.aria },
                            Like_Buttons: { count: getCount("button[aria-label*='Like'], button.react-button__trigger"), sample_aria: getSample("button[aria-label*='Like']")?.aria },
                            TipTap_Editors: { count: getCount("div[contenteditable='true'], div[role='textbox']"), sample_aria: getSample("div[contenteditable='true']")?.aria },
                            Post_Articles: { count: getCount("[role='article'], div[data-id], div.feed-shared-update-v2"), sample_aria: getSample("[role='article']")?.aria }
                        };
                    } else if (href.includes("linkedin.com/notifications")) {
                        metrics = {
                            Notification_Cards: { count: getCount("article.nt-card, div.notification-card, div.nt-card-content"), sample_aria: getSample("article.nt-card")?.aria },
                            Action_Buttons: { count: getCount("button[aria-label*='Reply'], button[aria-label*='More options']"), sample_aria: getSample("button[aria-label*='Reply']")?.aria },
                            Unread_Indicators: { count: getCount("span.nt-card__unread-indicator, div.nt-card--unread"), sample_aria: "" }
                        };
                    } else if (href.includes("linkedin.com/messaging")) {
                        metrics = {
                            Conversation_Items: { count: getCount("ul.msg-conversations-container__convo-list, div.msg-conversations-container__convo-item"), sample_aria: "" },
                            Message_Input: { count: getCount("div.msg-form__contenteditable, div[contenteditable='true']"), sample_aria: getSample("div.msg-form__contenteditable")?.aria },
                            Send_Button: { count: getCount("button.msg-form__send-button, button[type='submit']"), sample_aria: getSample("button.msg-form__send-button")?.aria }
                        };
                    } else if (href.includes("gemini.google.com")) {
                        metrics = {
                            Prompt_Rich_Input: { count: getCount("div.rich-textarea, div[contenteditable='true'], p.placeholder"), sample_aria: getSample("div.rich-textarea")?.aria },
                            Send_Prompt_Button: { count: getCount("button[aria-label*='Send'], button.send-button"), sample_aria: getSample("button[aria-label*='Send']")?.aria },
                            Model_Response_Cards: { count: getCount("message-content, div.model-response-text, div.markdown"), sample_aria: "" },
                            New_Chat_Button: { count: getCount("button[aria-label*='New chat']"), sample_aria: getSample("button[aria-label*='New chat']")?.aria }
                        };
                    } else {
                        metrics = {
                            All_Buttons: { count: getCount("button"), sample_aria: "" },
                            Inputs: { count: getCount("input, textarea, div[contenteditable='true']"), sample_aria: "" }
                        };
                    }

                    return {
                        url: href,
                        title: document.title,
                        metrics: metrics
                    };
                })()
            `;

            ws.send(JSON.stringify({
                id: 20,
                sessionId: sessionId,
                method: "Runtime.evaluate",
                params: { expression: domQueryScript, returnByValue: true }
            }));
        }

        function saveReportAndExit() {
            const report = {
                timestamp: new Date().toISOString(),
                total_pages: analysisResults.length,
                execution_type: "Native Node.js JS-Based CDP DOM Analysis",
                pages: analysisResults
            };

            fs.writeFileSync(REPORT_PATH, JSON.stringify(report, null, 2), 'utf-8');
            console.log(`\n===========================================================================`);
            console.log(`🎉 4-PAGE JS-BASED DOM ANALYSIS COMPLETE!`);
            console.log(`📁 Report Saved to: ${REPORT_PATH}`);
            console.log(`===========================================================================`);
            ws.close();
            process.exit(0);
        }

    } catch (err) {
        console.error("⚠️ Error in JS DOM Analysis Agent:", err.message);
    }
}

main();

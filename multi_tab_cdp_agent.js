const fs = require('fs');
const path = require('path');

const REPORT_PATH = "C:\\Users\\SIGMA\\.gemini\\antigravity-ide\\brain\\728c3d79-fe7b-4a11-9cd2-0486c8fc9c68\\multi_tab_cdp_analysis.json";

async function runMultiTabCDPAgent() {
    console.log("===========================================================================");
    console.log(" 🌐 MULTI-TAB LINKEDIN CDP AGENT — DOM ANALYSIS & TAB INSPECTION");
    console.log("===========================================================================");

    try {
        // Fetch all open browser targets
        const listRes = await fetch("http://127.0.0.1:9222/json/list");
        const allTargets = await listRes.json();

        // Filter page targets
        const pageTargets = allTargets.filter(t => t.type === 'page');
        const linkedinTargets = pageTargets.filter(t => t.url && t.url.includes("linkedin.com"));

        console.log(`📌 Total Open Browser Tabs: ${pageTargets.length}`);
        console.log(`📌 LinkedIn Specific Tabs : ${linkedinTargets.length}`);

        if (linkedinTargets.length === 0) {
            console.log("⚠️ No active LinkedIn tabs found. Navigating main tab to LinkedIn Feed...");
        }

        const tabsToProcess = linkedinTargets.length > 0 ? linkedinTargets : [pageTargets[0]];
        const multiTabResults = [];

        // Connect to Browser WebSocket
        const verRes = await fetch("http://127.0.0.1:9222/json/version");
        const versionInfo = await verRes.json();
        const browserWsUrl = versionInfo.webSocketDebuggerUrl;

        for (let i = 0; i < tabsToProcess.length; i++) {
            const target = tabsToProcess[i];
            console.log(`\n---------------------------------------------------------------------------`);
            console.log(`🔍 [Tab ${i + 1}/${tabsToProcess.length}] Target ID: ${target.id}`);
            console.log(`   Title : ${target.title || 'Untitled'}`);
            console.log(`   URL   : ${target.url}`);

            const tabAudit = await auditSingleTab(browserWsUrl, target);
            multiTabResults.push(tabAudit);
        }

        // Summary Report
        const finalReport = {
            timestamp: new Date().toISOString(),
            total_tabs_audited: multiTabResults.length,
            tabs: multiTabResults
        };

        fs.writeFileSync(REPORT_PATH, JSON.stringify(finalReport, null, 2), 'utf-8');
        console.log("\n===========================================================================");
        console.log(`🎉 MULTI-TAB CDP AGENT COMPLETE! Audited ${multiTabResults.length} tab(s).`);
        console.log(`📁 Saved report to: ${REPORT_PATH}`);
        console.log("===========================================================================");

    } catch (err) {
        console.error("⚠️ Multi-tab CDP Agent Error:", err.message);
    }
}

function auditSingleTab(browserWsUrl, target) {
    return new Promise((resolve) => {
        const ws = new WebSocket(browserWsUrl);

        let sessionId = null;

        ws.onopen = () => {
            // Activate Tab
            ws.send(JSON.stringify({ id: 1, method: "Target.activateTarget", params: { targetId: target.id } }));
        };

        ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);

            if (msg.id === 1) {
                // Attach to target
                ws.send(JSON.stringify({
                    id: 2,
                    method: "Target.attachToTarget",
                    params: { targetId: target.id, flatten: true }
                }));
            } else if (msg.id === 2) {
                sessionId = msg.result.sessionId;

                // Evaluate DOM elements
                const domQueryScript = `
                    (function() {
                        const getCount = (sel) => document.querySelectorAll(sel).length;
                        return {
                            url: window.location.href,
                            title: document.title,
                            Comment_Buttons: getCount("button[aria-label*='Comment']"),
                            Repost_Buttons: getCount("button[aria-label*='Repost']"),
                            Like_Buttons: getCount("button[aria-label*='Like'], button.react-button__trigger"),
                            TipTap_Editors: getCount("div[contenteditable='true'], div[role='textbox']"),
                            Post_Articles: getCount("[role='article'], div[data-id], div.feed-shared-update-v2"),
                            Navigation_Nav: getCount("nav.global-nav__nav"),
                            Chat_Windows: getCount("div.msg-convo-wrapper, div.msg-overlay-conversation-bubble"),
                            Notification_Items: getCount("article.nt-card, div.notification-card")
                        };
                    })()
                `;

                ws.send(JSON.stringify({
                    id: 3,
                    sessionId: sessionId,
                    method: "Runtime.evaluate",
                    params: { expression: domQueryScript, returnByValue: true }
                }));
            } else if (msg.id === 3) {
                const domData = msg.result.result ? msg.result.result.value : {};
                console.log(`   📊 DOM Summary:`);
                console.log(`      • Comment Buttons     : ${domData.Comment_Buttons || 0}`);
                console.log(`      • Repost Buttons      : ${domData.Repost_Buttons || 0}`);
                console.log(`      • TipTap Editors      : ${domData.TipTap_Editors || 0}`);
                console.log(`      • Chat Windows        : ${domData.Chat_Windows || 0}`);
                console.log(`      • Notification Cards  : ${domData.Notification_Items || 0}`);

                ws.close();
                resolve({
                    target_id: target.id,
                    url: target.url,
                    title: target.title,
                    dom_data: domData
                });
            }
        };

        ws.onerror = (err) => {
            console.error("   ⚠️ WebSocket error on tab:", err);
            ws.close();
            resolve({ target_id: target.id, url: target.url, error: "WebSocket Error" });
        };
    });
}

runMultiTabCDPAgent();

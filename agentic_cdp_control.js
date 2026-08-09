const fs = require('fs');
const path = require('path');

const REPORT_PATH = "C:\\Users\\SIGMA\\.gemini\\antigravity-ide\\brain\\728c3d79-fe7b-4a11-9cd2-0486c8fc9c68\\cdp_node_dom_analysis.json";

async function main() {
    console.log("===========================================================================");
    console.log(" 🔬 NODE.JS CDP AGENTIC CONTROL & LIVE DOM ANALYSIS (ZERO PYTHON)");
    console.log("===========================================================================");

    try {
        const res = await fetch("http://127.0.0.1:9222/json/version");
        const versionInfo = await res.json();
        const wsUrl = versionInfo.webSocketDebuggerUrl;
        console.log(`🔗 Connecting to CDP WebSocket: ${wsUrl}`);

        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            ws.send(JSON.stringify({ id: 1, method: "Target.getTargets" }));
        };

        let pageTargetId = null;

        ws.onmessage = async (event) => {
            const response = JSON.parse(event.data);

            if (response.id === 1) {
                const targets = response.result.targetInfos.filter(t => t.type === 'page');
                let linkedinTarget = targets.find(t => t.url && t.url.includes("linkedin.com"));
                
                if (!linkedinTarget && targets.length > 0) {
                    // Use the first active page target
                    linkedinTarget = targets[0];
                    console.log(`📌 Navigating active tab (${linkedinTarget.url}) to https://www.linkedin.com/feed/ ...`);
                }

                if (linkedinTarget) {
                    pageTargetId = linkedinTarget.targetId;
                    console.log(`📌 Target Page ID: ${pageTargetId} (${linkedinTarget.title || 'Tab'})`);
                    
                    // Activate Tab
                    ws.send(JSON.stringify({ id: 2, method: "Target.activateTarget", params: { targetId: pageTargetId } }));
                } else {
                    console.log("⚠️ No page targets found.");
                    process.exit(1);
                }
            } else if (response.id === 2) {
                console.log("⚡ Tab Focused!");
                
                // Attach to Page Target
                ws.send(JSON.stringify({
                    id: 3,
                    method: "Target.attachToTarget",
                    params: { targetId: pageTargetId, flatten: true }
                }));
            } else if (response.id === 3) {
                const sessionId = response.result.sessionId;
                console.log(`🔌 Attached to Page Target Session: ${sessionId}`);

                // Ensure page is on LinkedIn Feed
                ws.send(JSON.stringify({
                    id: 10,
                    sessionId: sessionId,
                    method: "Page.navigate",
                    params: { url: "https://www.linkedin.com/feed/" }
                }));

                setTimeout(() => {
                    // Evaluate DOM elements via Runtime.evaluate in Page context
                    const domQueryScript = `
                        (function() {
                            const getCount = (sel) => document.querySelectorAll(sel).length;
                            const getSample = (sel) => {
                                const el = document.querySelector(sel);
                                return el ? { tag: el.tagName, aria: el.getAttribute('aria-label') || '' } : null;
                            };
                            return {
                                Comment_Buttons: { count: getCount("button[aria-label*='Comment']"), sample: getSample("button[aria-label*='Comment']") },
                                Repost_Buttons: { count: getCount("button[aria-label*='Repost']"), sample: getSample("button[aria-label*='Repost']") },
                                Like_Buttons: { count: getCount("button[aria-label*='Like'], button.react-button__trigger"), sample: getSample("button[aria-label*='Like']") },
                                TipTap_Editors: { count: getCount("div[contenteditable='true'], div[role='textbox']"), sample: getSample("div[contenteditable='true']") },
                                Post_Articles: { count: getCount("[role='article'], div[data-id], div.feed-shared-update-v2"), sample: getSample("[role='article']") },
                                Search_Input: { count: getCount("input[aria-label*='Search']"), sample: getSample("input[aria-label*='Search']") }
                            };
                        })()
                    `;

                    ws.send(JSON.stringify({
                        id: 4,
                        sessionId: sessionId,
                        method: "Runtime.evaluate",
                        params: { expression: domQueryScript, returnByValue: true }
                    }));
                }, 5000);
            } else if (response.id === 4) {
                const domData = response.result.result.value;
                console.log("\n📊 LIVE DOM ELEMENT BREAKDOWN ON LINKEDIN FEED:");
                for (const [key, val] of Object.entries(domData)) {
                    const ariaStr = val.sample ? val.sample.aria : '';
                    console.log(`   • ${key.padEnd(20)}: ${val.count} found (aria='${ariaStr}')`);
                }

                // Write Report to Disk
                const report = {
                    page_url: "https://www.linkedin.com/feed/",
                    timestamp: new Date().toISOString(),
                    dom_elements: domData,
                    execution_engine: "Native Node.js CDP Protocol"
                };

                fs.writeFileSync(REPORT_PATH, JSON.stringify(report, null, 2), 'utf-8');
                console.log(`\n📁 DOM Analysis Report saved to: ${REPORT_PATH}`);
                console.log("===========================================================================");
                console.log("🎉 CDP AGENTIC CONTROL & DOM ANALYSIS COMPLETE!");
                console.log("===========================================================================");
                ws.close();
                process.exit(0);
            }
        };

    } catch (err) {
        console.error("⚠️ Error during CDP execution:", err.message);
    }
}

main();

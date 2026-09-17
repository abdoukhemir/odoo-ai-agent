/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { DiscussChannelPreview } from "@mail/core/common/discuss_channel_preview/discuss_channel_preview";
import { Thread } from "@mail/core/common/thread/thread";

// Inject dynamic CSS directly into the page to bypass Odoo's scoping
function injectBotStyles() {
    const styleId = "n8n_bot_styles";
    
    // Don't inject twice
    if (document.getElementById(styleId)) {
        return;
    }
    
    const style = document.createElement("style");
    style.id = styleId;
    style.textContent = `
        /* N8N Assistant Bot - Forced Styling */
        [data-name="N8N Assistant"],
        .n8n-bot-channel {
            background-color: rgba(76, 175, 80, 0.15) !important;
            border-left: 4px solid #4CAF50 !important;
            border-radius: 0 8px 8px 0;
        }
        
        [data-name="N8N Assistant"]:hover,
        .n8n-bot-channel:hover {
            background: rgba(76, 175, 80, 0.25) !important;
        }
        
        [data-name="N8N Assistant"] span,
        .n8n-bot-channel span {
            color: #2e7d32 !important;
            font-weight: 700 !important;
        }
        
        [data-name="N8N Assistant"] .o_mail_avatar,
        .n8n-bot-channel .o_mail_avatar {
            box-shadow: 0 0 8px rgba(76, 175, 80, 0.6) !important;
            filter: brightness(1.1);
        }
    `;
    
    document.head.appendChild(style);
    console.log("[N8N Bot] Styles injected");
}

// Initialize on load
injectBotStyles();

// Listen for style sheet load events
document.addEventListener("load", injectBotStyles, true);

// Use MutationObserver for real-time updates
const observer = new MutationObserver(() => {
    updateN8NBotDisplay();
});

if (document.body) {
    observer.observe(document.body, {
        childList: true,
        subtree: true,
        characterData: false,
    });
}

// Initial update
setTimeout(updateN8NBotDisplay, 500);
setTimeout(updateN8NBotDisplay, 1000);

function updateN8NBotDisplay() {
    try {
        // Find all channel preview elements
        const channels = document.querySelectorAll(".o_discuss_ChannelPreview");
        
        channels.forEach(element => {
            const titleAttr = element.getAttribute("title") || "";
            const ariaLabel = element.getAttribute("aria-label") || "";
            const text = element.textContent || "";
            
            // Check if this is the N8N Assistant channel
            const isN8N = 
                titleAttr === "N8N Assistant" || 
                ariaLabel === "N8N Assistant" || 
                text.trim() === "N8N Assistant" ||
                text.includes("N8N Assistant");
            
            if (isN8N) {
                console.log("[N8N Bot] Found N8N Assistant channel, applying styles");
                
                // Mark as N8N bot with data attribute
                element.setAttribute("data-name", "N8N Assistant");
                element.setAttribute("title", "N8N Assistant");
                element.classList.add("n8n-bot-channel");
                
                // Apply inline styles as immediate fallback
                element.style.backgroundColor = "rgba(76, 175, 80, 0.15)";
                element.style.borderLeft = "4px solid #4CAF50";
                element.style.borderRadius = "0 8px 8px 0";
                
                // Find and update all text elements
                const allSpans = element.querySelectorAll("span, div");
                allSpans.forEach(span => {
                    const spanText = span.textContent?.trim();
                    
                    if (spanText === "N8N Assistant") {
                        // Update with emoji
                        span.textContent = "🤖 N8N Assistant";
                        span.style.fontWeight = "700";
                        span.style.color = "#2e7d32";
                        span.style.fontSize = "13px";
                        console.log("[N8N Bot] Updated channel name with emoji");
                    }
                });
                
                // Style the avatar if present
                const avatar = element.querySelector(".o_mail_avatar");
                if (avatar) {
                    avatar.style.boxShadow = "0 0 8px rgba(76, 175, 80, 0.6)";
                    avatar.style.filter = "brightness(1.1)";
                }
            }
        });
    } catch (e) {
        console.error("[N8N Bot] Error updating display:", e);
    }
}

// Re-update regularly to catch dynamically added channels
setInterval(updateN8NBotDisplay, 1000);

// Re-inject styles when assets reload
if (window.owl && window.owl.ComponentExtension) {
    window.addEventListener("owl_resize", () => {
        injectBotStyles();
        updateN8NBotDisplay();
    });
}
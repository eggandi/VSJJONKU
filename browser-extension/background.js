importScripts("common.js");

const DEFAULT_STATE = {
    relayUrl: "",
    agentId: "default",
    webToken: "",
    autoQueue: false,
    pending: [],
    lastStatus: "",
};

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    handleMessage(message)
        .then((value) => sendResponse({ ok: true, value }))
        .catch((error) => sendResponse({ ok: false, error: error.message }));
    return true;
});

async function handleMessage(message) {
    if (!message || typeof message.type !== "string") {
        throw new Error("Invalid extension message.");
    }
    if (message.type === "getState") {
        return getState();
    }
    if (message.type === "saveConfig") {
        return saveConfig(message.config);
    }
    if (message.type === "captureActions") {
        return captureActions(message.actions, message.source);
    }
    if (message.type === "queuePending") {
        return queuePending(message.index, message.confirmDestructive === true);
    }
    if (message.type === "clearPending") {
        await chrome.storage.local.set({ pending: [] });
        return getState();
    }
    throw new Error("Unsupported extension message.");
}

async function getState() {
    return { ...DEFAULT_STATE, ...(await chrome.storage.local.get(DEFAULT_STATE)) };
}

async function saveConfig(config) {
    if (!config || typeof config !== "object") {
        throw new Error("Invalid Relay configuration.");
    }
    const relayUrl = validateRelayUrl(config.relayUrl);
    const agentId = validateAgentId(config.agentId);
    if (typeof config.webToken !== "string" || config.webToken.length < 32) {
        throw new Error("Relay web token must contain at least 32 characters.");
    }
    if (typeof config.autoQueue !== "boolean") {
        throw new Error("Automatic queue setting is invalid.");
    }
    const originPattern = `${new URL(relayUrl).origin}/*`;
    const permission = await chrome.permissions.contains({ origins: [originPattern] });
    if (!permission && !(originPattern.startsWith("http://127.0.0.1") || originPattern.startsWith("http://localhost"))) {
        const granted = await chrome.permissions.request({ origins: [originPattern] });
        if (!granted) {
            throw new Error("Relay host permission was not granted.");
        }
    }
    await chrome.storage.local.set({ relayUrl, agentId, webToken: config.webToken, autoQueue: config.autoQueue });
    return getState();
}

async function captureActions(actions, source) {
    if (!Array.isArray(actions) || (source !== "selection" && source !== "automatic")) {
        throw new Error("Invalid captured actions.");
    }
    const valid = actions.filter((action) => action && typeof action.method === "string" && action.params && typeof action.params === "object");
    const state = await getState();
    const pending = [...state.pending];
    for (const action of valid) {
        if (source === "automatic" && state.autoQueue && !VSJJONKU.isDestructive(action.method)) {
            try {
                await queueAction(state, action, false);
                state.lastStatus = `Automatically queued ${action.method}.`;
                continue;
            } catch (error) {
                state.lastStatus = `Automatic queue failed: ${error.message}`;
            }
        }
        const key = VSJJONKU.actionKey(action);
        if (!pending.some((item) => VSJJONKU.actionKey(item) === key)) {
            pending.push(action);
        }
    }
    await chrome.storage.local.set({ pending: pending.slice(-20), lastStatus: state.lastStatus });
    return getState();
}

async function queuePending(index, confirmDestructive) {
    const state = await getState();
    if (!Number.isInteger(index) || index < 0 || index >= state.pending.length) {
        throw new Error("Selected action is unavailable.");
    }
    const action = state.pending[index];
    const response = await queueAction(state, action, confirmDestructive);
    const pending = state.pending.filter((_, itemIndex) => itemIndex !== index);
    await chrome.storage.local.set({ pending, lastStatus: `Queued ${action.method}: ${response.requestId}` });
    return getState();
}

async function queueAction(state, action, confirmDestructive) {
    const relayUrl = validateRelayUrl(state.relayUrl);
    const agentId = validateAgentId(state.agentId);
    if (typeof state.webToken !== "string" || state.webToken.length < 32) {
        throw new Error("Configure a Relay web token first.");
    }
    if (VSJJONKU.isDestructive(action.method) && !confirmDestructive) {
        throw new Error("Destructive actions require the confirmation checkbox.");
    }
    const response = await fetch(`${relayUrl}/api/commands`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-VSJJONKU-Web-Token": state.webToken,
        },
        body: JSON.stringify({
            agentId,
            method: action.method,
            params: action.params,
            confirm: VSJJONKU.isDestructive(action.method) && confirmDestructive,
        }),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(body.detail || "Relay rejected the action.");
    }
    return body;
}

function validateRelayUrl(value) {
    if (typeof value !== "string") {
        throw new Error("Relay URL is required.");
    }
    let url;
    try {
        url = new URL(value);
    } catch {
        throw new Error("Relay URL is invalid.");
    }
    const loopback = url.hostname === "127.0.0.1" || url.hostname === "localhost";
    if (url.protocol !== "https:" && !(url.protocol === "http:" && loopback)) {
        throw new Error("Relay must use HTTPS, except for loopback development.");
    }
    if (url.username || url.password || url.search || url.hash) {
        throw new Error("Relay URL must not include credentials, a query, or a fragment.");
    }
    return url.toString().replace(/\/$/, "");
}

function validateAgentId(value) {
    if (typeof value !== "string" || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(value)) {
        throw new Error("Relay agent ID is invalid.");
    }
    return value;
}

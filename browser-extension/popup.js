const form = {
    relayUrl: document.getElementById("relayUrl"),
    agentId: document.getElementById("agentId"),
    webToken: document.getElementById("webToken"),
    autoQueue: document.getElementById("autoQueue"),
};
const statusElement = document.getElementById("status");
const pendingElement = document.getElementById("pending");

function send(message) {
    return new Promise((resolve, reject) => {
        chrome.runtime.sendMessage(message, (response) => {
            if (chrome.runtime.lastError) {
                reject(new Error(chrome.runtime.lastError.message));
            } else if (!response?.ok) {
                reject(new Error(response?.error || "Extension request failed."));
            } else {
                resolve(response.value);
            }
        });
    });
}

function showStatus(text, error = false) {
    statusElement.textContent = text || "";
    statusElement.style.color = error ? "#a40000" : "";
}

function isDestructive(method) {
    return ["change_file", "delete_file", "delete_directory"].includes(method);
}

function render(state) {
    form.relayUrl.value = state.relayUrl;
    form.agentId.value = state.agentId;
    form.webToken.value = state.webToken;
    form.autoQueue.checked = state.autoQueue;
    showStatus(state.lastStatus || "");
    pendingElement.replaceChildren();
    if (!state.pending.length) {
        pendingElement.textContent = "대기 중인 작업이 없습니다.";
        return;
    }
    state.pending.forEach((action, index) => {
        const block = document.createElement("section");
        block.className = "pending";
        const title = document.createElement("div");
        title.textContent = action.method;
        if (isDestructive(action.method)) {
            title.className = "danger";
            title.textContent += " (변경/삭제)";
        }
        const params = document.createElement("pre");
        params.textContent = JSON.stringify(action.params, null, 2);
        const confirm = document.createElement("label");
        confirm.className = "inline";
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.disabled = !isDestructive(action.method);
        confirm.append(checkbox, document.createTextNode(" 변경/삭제 실행 확인"));
        const queue = document.createElement("button");
        queue.textContent = "Relay로 보내기";
        queue.addEventListener("click", async () => {
            try {
                render(await send({ type: "queuePending", index, confirmDestructive: checkbox.checked }));
            } catch (error) {
                showStatus(error.message, true);
            }
        });
        block.append(title, params, confirm, queue);
        pendingElement.append(block);
    });
}

document.getElementById("save").addEventListener("click", async () => {
    try {
        render(await send({
            type: "saveConfig",
            config: {
                relayUrl: form.relayUrl.value.trim(),
                agentId: form.agentId.value.trim(),
                webToken: form.webToken.value,
                autoQueue: form.autoQueue.checked,
            },
        }));
    } catch (error) {
        showStatus(error.message, true);
    }
});

document.getElementById("clear").addEventListener("click", async () => {
    try {
        render(await send({ type: "clearPending" }));
    } catch (error) {
        showStatus(error.message, true);
    }
});

send({ type: "getState" }).then(render).catch((error) => showStatus(error.message, true));

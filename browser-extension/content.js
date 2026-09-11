(() => {
    const seen = new Set();

    function publish(actions, source) {
        const fresh = actions.filter((action) => {
            const key = VSJJONKU.actionKey(action);
            if (source !== "selection" && seen.has(key)) {
                return false;
            }
            seen.add(key);
            return true;
        });
        if (fresh.length > 0) {
            chrome.runtime.sendMessage({ type: "captureActions", source, actions: fresh });
        }
    }

    document.addEventListener("selectionchange", () => {
        const selection = window.getSelection()?.toString() ?? "";
        publish(VSJJONKU.parseTaggedActions(selection), "selection");
    });

    const observer = new MutationObserver((records) => {
        for (const record of records) {
            for (const node of record.addedNodes) {
                const text = node.textContent ?? "";
                publish(VSJJONKU.parseTaggedActions(text), "automatic");
            }
        }
    });
    observer.observe(document.documentElement, { childList: true, subtree: true });
})();

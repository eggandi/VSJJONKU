globalThis.VSJJONKU = (() => {
    const methods = new Set([
        "list_directory", "read_file", "search_code", "git_status", "git_diff",
        "write_file", "create_directory", "change_file", "delete_file", "delete_directory",
    ]);
    const destructiveMethods = new Set(["change_file", "delete_file", "delete_directory"]);
    const marker = "[VSJJONKU_EXEC]";

    function parseTaggedActions(text) {
        if (typeof text !== "string" || !text.includes(marker)) {
            return [];
        }
        const actions = [];
        const pattern = /\[VSJJONKU_EXEC\]\s*```(?:json)?\s*([\s\S]*?)```/g;
        for (const match of text.matchAll(pattern)) {
            try {
                const value = JSON.parse(match[1]);
                if (isAction(value)) {
                    actions.push({ method: value.method, params: value.params });
                }
            } catch {
                // A partially streamed or malformed ChatGPT response is ignored.
            }
        }
        return actions;
    }

    function isAction(value) {
        return (
            value &&
            typeof value === "object" &&
            !Array.isArray(value) &&
            methods.has(value.method) &&
            value.params &&
            typeof value.params === "object" &&
            !Array.isArray(value.params)
        );
    }

    function isDestructive(method) {
        return destructiveMethods.has(method);
    }

    function actionKey(action) {
        return `${action.method}:${JSON.stringify(action.params)}`;
    }

    return { actionKey, isDestructive, marker, parseTaggedActions };
})();

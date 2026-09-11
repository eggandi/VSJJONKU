const assert = require("node:assert/strict");

require("./common.js");

const actions = globalThis.VSJJONKU.parseTaggedActions(
    '[VSJJONKU_EXEC]\n```json\n{"method":"read_file","params":{"path":"README.md"}}\n```'
);
assert.deepEqual(actions, [{ method: "read_file", params: { path: "README.md" } }]);
assert.equal(globalThis.VSJJONKU.parseTaggedActions("no marker").length, 0);
assert.equal(globalThis.VSJJONKU.parseTaggedActions('[VSJJONKU_EXEC]\n```json\n{"method":"exec","params":{}}\n```').length, 0);
assert.equal(globalThis.VSJJONKU.isDestructive("delete_directory"), true);
assert.equal(globalThis.VSJJONKU.isDestructive("read_file"), false);
console.log("browser action parser tests passed");

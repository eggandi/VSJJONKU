const assert = require("node:assert/strict");
const test = require("node:test");

const { allowsFolder, parseFolderPolicy } = require("../out/folder_policy.js");

const policy = parseFolderPolicy(JSON.stringify({
    version: 1,
    rules: [
        { path: ".", permissions: { read: true } },
        { path: "src", permissions: { write: true, change: true } },
        { path: "src/generated", permissions: { change: false } },
    ],
}));

test("inherits and overrides folder permissions", () => {
    assert.equal(allowsFolder(policy, "docs", "read"), true);
    assert.equal(allowsFolder(policy, "src", "write"), true);
    assert.equal(allowsFolder(policy, "src/lib", "change"), true);
    assert.equal(allowsFolder(policy, "src/generated", "change"), false);
    assert.equal(allowsFolder(policy, "src/generated", "delete"), false);
});

test("rejects invalid policy paths and permissions", () => {
    assert.throws(
        () => parseFolderPolicy('{"version":1,"rules":[{"path":"../secret","permissions":{"read":true}}]}'),
        /relative directories/,
    );
    assert.throws(
        () => parseFolderPolicy('{"version":1,"rules":[{"path":"src","permissions":{"owner":true}}]}'),
        /invalid permission/,
    );
});

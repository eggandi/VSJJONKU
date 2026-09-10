import { execFile } from "node:child_process";
import { timingSafeEqual } from "node:crypto";
import { readFileSync } from "node:fs";
import { createServer, IncomingMessage, Server, ServerResponse } from "node:http";
import { isAbsolute, relative, resolve } from "node:path";
import { promisify } from "node:util";
import * as vscode from "vscode";

import {
    allowsFolder,
    Capability,
    FolderPolicy,
    normalizeFolderPath,
    parseFolderPolicy,
} from "./folder_policy";

const execFileAsync = promisify(execFile);
const MAX_REQUEST_BYTES = 64 * 1024;
const MAX_FILE_BYTES = 1024 * 1024;
const MAX_SEARCH_FILES = 500;
const MAX_SEARCH_MATCHES = 200;
const EXCLUDED_DIRECTORIES = new Set([".git", "node_modules", ".venv"]);
const DENIED_DIRECTORY_NAMES = new Set([".ssh", ".aws", ".gnupg"]);
const DENIED_FILE_NAMES = new Set([
    ".env",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "known_hosts",
    "credentials",
    "credentials.json",
]);
const DENIED_FILE_SUFFIXES = [".pem", ".key", ".pfx", ".p12"];

type RpcRequest = {
    method: string;
    params?: Record<string, unknown>;
};

type SearchMatch = {
    path: string;
    line: number;
    text: string;
};

export async function activate(context: vscode.ExtensionContext): Promise<void> {
    const configuredPort = vscode.workspace
        .getConfiguration("vsjjonku")
        .get<number>("bridgePort", 38991);
    const port = readBridgePort(process.env.VSJJONKU_BRIDGE_PORT, configuredPort);
    const bridgeToken = readBridgeToken(process.env.VSJJONKU_BRIDGE_TOKEN);
    const policy = await loadFolderPolicy(process.env.VSJJONKU_POLICY_PATH);
    const bridge = createServer((request, response) => {
        void handleRequest(request, response, bridgeToken, policy);
    });

    bridge.listen(port, "127.0.0.1");
    context.subscriptions.push(closeServer(bridge));
}

async function loadFolderPolicy(policyPath: string | undefined): Promise<FolderPolicy> {
    if (!policyPath || !isAbsolute(policyPath)) {
        throw new Error("VSJJONKU_POLICY_PATH must be an absolute path outside the Workspace.");
    }
    const root = workspaceRoot();
    const resolvedPath = resolve(policyPath);
    if (root.scheme === "file" && isInsideWorkspace(root.fsPath, resolvedPath)) {
        throw new Error("VSJJONKU_POLICY_PATH must be outside the Workspace.");
    }
    let policy: FolderPolicy;
    try {
        policy = parseFolderPolicy(readFileSync(resolvedPath, "utf8"));
    } catch (error) {
        if (error instanceof Error) {
            throw new Error(`Could not load folder policy: ${error.message}`);
        }
        throw new Error("Could not load folder policy.");
    }
    for (const rule of policy.rules) {
        const directory = await workspaceUri(rule.path);
        const stat = await vscode.workspace.fs.stat(directory);
        if ((stat.type & vscode.FileType.Directory) === 0) {
            throw new Error(`Folder policy path is not a directory: ${rule.path}`);
        }
    }
    return policy;
}

function isInsideWorkspace(workspacePath: string, candidatePath: string): boolean {
    const difference = relative(resolve(workspacePath), candidatePath);
    return difference === "" || (!difference.startsWith("..") && !isAbsolute(difference));
}

function readBridgeToken(value: string | undefined): string {
    if (!value || value.length < 32) {
        throw new Error("VSJJONKU_BRIDGE_TOKEN must contain at least 32 characters.");
    }
    return value;
}

function readBridgePort(environmentValue: string | undefined, configuredPort: number): number {
    if (environmentValue === undefined) {
        return configuredPort;
    }
    const parsed = Number(environmentValue);
    if (!Number.isInteger(parsed) || parsed < 1024 || parsed > 65535) {
        throw new Error("VSJJONKU_BRIDGE_PORT must be a valid TCP port.");
    }
    return parsed;
}

function closeServer(server: Server): vscode.Disposable {
    return new vscode.Disposable(() => server.close());
}

async function handleRequest(
    request: IncomingMessage,
    response: ServerResponse,
    bridgeToken: string,
    policy: FolderPolicy,
): Promise<void> {
    if (!isAuthorized(request, bridgeToken)) {
        return send(response, 401, { ok: false, error: "Unauthorized." });
    }

    if (request.method === "GET" && request.url === "/health") {
        return send(response, 200, { ok: true, result: { status: "ready" } });
    }

    if (request.method !== "POST" || request.url !== "/rpc") {
        return send(response, 404, { ok: false, error: "Not found." });
    }

    try {
        const rpc = parseRpcRequest(await readBody(request));
        const result = await dispatch(rpc, policy);
        return send(response, 200, { ok: true, result });
    } catch (error) {
        const message = error instanceof Error ? error.message : "Bridge request failed.";
        return send(response, 400, { ok: false, error: message });
    }
}

function isAuthorized(request: IncomingMessage, bridgeToken: string): boolean {
    const authorization = request.headers.authorization;
    const expected = Buffer.from(`Bearer ${bridgeToken}`);
    const received = Buffer.from(authorization ?? "");
    return expected.length === received.length && timingSafeEqual(expected, received);
}

function readBody(request: IncomingMessage): Promise<string> {
    return new Promise((resolve, reject) => {
        let size = 0;
        const chunks: Buffer[] = [];
        request.on("data", (chunk: Buffer) => {
            size += chunk.length;
            if (size > MAX_REQUEST_BYTES) {
                reject(new Error("Request body is too large."));
                request.destroy();
                return;
            }
            chunks.push(chunk);
        });
        request.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
        request.on("error", reject);
    });
}

function parseRpcRequest(body: string): RpcRequest {
    let parsed: unknown;
    try {
        parsed = JSON.parse(body);
    } catch {
        throw new Error("Request body must be JSON.");
    }
    if (
        typeof parsed !== "object" ||
        parsed === null ||
        typeof (parsed as { method?: unknown }).method !== "string"
    ) {
        throw new Error("Request must contain a method.");
    }
    return parsed as RpcRequest;
}

async function dispatch(request: RpcRequest, policy: FolderPolicy): Promise<unknown> {
    const params = request.params ?? {};
    switch (request.method) {
        case "list_directory":
            return listDirectory(readOptionalString(params, "path", "."), policy);
        case "read_file":
            return readFile(readRequiredString(params, "path"), policy);
        case "search_code":
            return searchCode(
                readRequiredString(params, "query"),
                readOptionalString(params, "path", "."),
                policy,
            );
        case "write_file":
            return writeNewFile(
                readRequiredString(params, "path"),
                readRequiredString(params, "content"),
                policy,
            );
        case "change_file":
            return changeFile(
                readRequiredString(params, "path"),
                readRequiredString(params, "content"),
                policy,
            );
        case "delete_file":
            return deleteFile(readRequiredString(params, "path"), policy);
        case "git_status":
            assertFolderPermission(policy, ".", "read");
            return runGit(["status", "--short", "--branch"]);
        case "git_diff":
            assertFolderPermission(policy, ".", "read");
            return runGit(["diff", "--no-ext-diff"]);
        default:
            throw new Error("Unsupported Bridge method.");
    }
}

function workspaceRoot(): vscode.Uri {
    const folders = vscode.workspace.workspaceFolders;
    if (!folders || folders.length !== 1) {
        throw new Error("Exactly one Workspace folder must be open.");
    }
    return folders[0].uri;
}

async function workspaceUri(relativePath: string): Promise<vscode.Uri> {
    const parts = validateRelativePath(relativePath);
    let current = workspaceRoot();
    for (const part of parts) {
        current = vscode.Uri.joinPath(current, part);
        const stat = await vscode.workspace.fs.stat(current);
        if ((stat.type & vscode.FileType.SymbolicLink) !== 0) {
            throw new Error("Symbolic links are not accessible.");
        }
    }
    return current;
}

function validateRelativePath(relativePath: string): string[] {
    if (relativePath.length === 0 || relativePath.startsWith("/") || relativePath.startsWith("\\")) {
        throw new Error("Path must be relative to the Workspace root.");
    }
    const parts = relativePath.split(/[\\/]+/).filter((part) => part !== "" && part !== ".");
    if (parts.some((part) => part === "..")) {
        throw new Error("Path traversal is not allowed.");
    }
    if (parts.some(isDeniedPathPart)) {
        throw new Error("Sensitive paths are not accessible.");
    }
    return parts;
}

async function listDirectory(
    path: string,
    policy: FolderPolicy,
): Promise<Array<{ name: string; type: string }>> {
    const directory = await workspaceUri(path);
    const stat = await vscode.workspace.fs.stat(directory);
    if ((stat.type & vscode.FileType.Directory) === 0) {
        throw new Error("Path is not a directory.");
    }
    assertFolderPermission(policy, path, "read");
    const entries = await vscode.workspace.fs.readDirectory(directory);
    return entries
        .filter(([name, type]) => {
            if (isDeniedPathPart(name) || (type & vscode.FileType.SymbolicLink) !== 0) {
                return false;
            }
            if ((type & vscode.FileType.Directory) === 0) {
                return true;
            }
            return allowsFolder(policy, joinFolderPath(path, name), "read");
        })
        .map(([name, type]) => ({ name, type: fileTypeName(type) }));
}

async function readFile(path: string, policy: FolderPolicy): Promise<{ path: string; content: string }> {
    const file = await workspaceUri(path);
    const stat = await vscode.workspace.fs.stat(file);
    if ((stat.type & vscode.FileType.File) === 0) {
        throw new Error("Path is not a file.");
    }
    assertFolderPermission(policy, parentFolderPath(path), "read");
    const bytes = await vscode.workspace.fs.readFile(file);
    if (bytes.byteLength > MAX_FILE_BYTES) {
        throw new Error("File exceeds the read size limit.");
    }
    return { path, content: new TextDecoder("utf-8", { fatal: true }).decode(bytes) };
}

async function writeNewFile(
    path: string,
    content: string,
    policy: FolderPolicy,
): Promise<{ path: string; bytesWritten: number }> {
    const file = await newWorkspaceFileUri(path);
    assertFolderPermission(policy, parentFolderPath(path), "write");
    if (await workspacePathExists(file)) {
        throw new Error("File already exists; use change_file to replace it.");
    }
    const bytes = encodeContent(content);
    await vscode.workspace.fs.writeFile(file, bytes);
    return { path, bytesWritten: bytes.byteLength };
}

async function changeFile(
    path: string,
    content: string,
    policy: FolderPolicy,
): Promise<{ path: string; bytesWritten: number }> {
    const file = await workspaceUri(path);
    const stat = await vscode.workspace.fs.stat(file);
    if ((stat.type & vscode.FileType.File) === 0) {
        throw new Error("Path is not a file.");
    }
    assertFolderPermission(policy, parentFolderPath(path), "change");
    const bytes = encodeContent(content);
    await vscode.workspace.fs.writeFile(file, bytes);
    return { path, bytesWritten: bytes.byteLength };
}

async function deleteFile(path: string, policy: FolderPolicy): Promise<{ path: string; deleted: true }> {
    const file = await workspaceUri(path);
    const stat = await vscode.workspace.fs.stat(file);
    if ((stat.type & vscode.FileType.File) === 0) {
        throw new Error("delete_file only permits a single file; recursive deletion is not supported.");
    }
    assertFolderPermission(policy, parentFolderPath(path), "delete");
    await vscode.workspace.fs.delete(file, { recursive: false, useTrash: false });
    return { path, deleted: true };
}

function encodeContent(content: string): Uint8Array {
    const bytes = new TextEncoder().encode(content);
    if (bytes.byteLength > MAX_FILE_BYTES) {
        throw new Error("Content exceeds the write size limit.");
    }
    return bytes;
}

async function newWorkspaceFileUri(path: string): Promise<vscode.Uri> {
    const parts = validateRelativePath(path);
    if (parts.length === 0) {
        throw new Error("File path must not be the Workspace root.");
    }
    const parent = await workspaceUri(parts.slice(0, -1).join("/") || ".");
    const parentStat = await vscode.workspace.fs.stat(parent);
    if ((parentStat.type & vscode.FileType.Directory) === 0) {
        throw new Error("File parent is not a directory.");
    }
    return vscode.Uri.joinPath(parent, parts[parts.length - 1]);
}

async function workspacePathExists(path: vscode.Uri): Promise<boolean> {
    try {
        await vscode.workspace.fs.stat(path);
        return true;
    } catch (error) {
        if (error instanceof vscode.FileSystemError && error.code === "FileNotFound") {
            return false;
        }
        throw error;
    }
}

async function searchCode(
    query: string,
    path: string,
    policy: FolderPolicy,
): Promise<{ matches: SearchMatch[]; truncated: boolean }> {
    if (query.length === 0 || query.length > 200) {
        throw new Error("Query must contain 1 to 200 characters.");
    }
    const scope = await workspaceUri(path);
    const files: vscode.Uri[] = [];
    const scopeStat = await vscode.workspace.fs.stat(scope);
    const scopeFolder = (scopeStat.type & vscode.FileType.Directory) !== 0
        ? path
        : parentFolderPath(path);
    assertFolderPermission(policy, scopeFolder, "read");
    const reachedLimit = (scopeStat.type & vscode.FileType.Directory) !== 0
        ? await collectFiles(scope, files, policy)
        : addFile(scope, files);
    const matches: SearchMatch[] = [];
    for (const file of files) {
        if (matches.length >= MAX_SEARCH_MATCHES) {
            return { matches, truncated: true };
        }
        let bytes: Uint8Array;
        try {
            bytes = await vscode.workspace.fs.readFile(file);
        } catch {
            continue;
        }
        if (bytes.byteLength > MAX_FILE_BYTES) {
            continue;
        }
        let content: string;
        try {
            content = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
        } catch {
            continue;
        }
        for (const [index, line] of content.split(/\r?\n/).entries()) {
            if (line.includes(query)) {
                matches.push({ path: vscode.workspace.asRelativePath(file, false), line: index + 1, text: line });
                if (matches.length >= MAX_SEARCH_MATCHES) {
                    return { matches, truncated: true };
                }
            }
        }
    }
    return { matches, truncated: reachedLimit };
}

async function collectFiles(
    directory: vscode.Uri,
    files: vscode.Uri[],
    policy: FolderPolicy,
): Promise<boolean> {
    for (const [name, type] of await vscode.workspace.fs.readDirectory(directory)) {
        if (files.length >= MAX_SEARCH_FILES) {
            return true;
        }
        if (
            EXCLUDED_DIRECTORIES.has(name) ||
            isDeniedPathPart(name) ||
            (type & vscode.FileType.SymbolicLink) !== 0
        ) {
            continue;
        }
        const child = vscode.Uri.joinPath(directory, name);
        if ((type & vscode.FileType.Directory) !== 0) {
            const childFolder = vscode.workspace.asRelativePath(child, false) || ".";
            if (!allowsFolder(policy, childFolder, "read")) {
                continue;
            }
            if (await collectFiles(child, files, policy)) {
                return true;
            }
        } else if ((type & vscode.FileType.File) !== 0 && addFile(child, files)) {
            return true;
        }
    }
    return false;
}

function assertFolderPermission(
    policy: FolderPolicy,
    folderPath: string,
    capability: Capability,
): void {
    if (!allowsFolder(policy, folderPath, capability)) {
        throw new Error(`Folder does not allow ${capability}.`);
    }
}

function parentFolderPath(path: string): string {
    const normalized = normalizeFolderPath(path);
    const separator = normalized.lastIndexOf("/");
    return separator === -1 ? "." : normalized.slice(0, separator);
}

function joinFolderPath(parent: string, child: string): string {
    const normalizedParent = normalizeFolderPath(parent);
    return normalizedParent === "." ? child : `${normalizedParent}/${child}`;
}

function addFile(file: vscode.Uri, files: vscode.Uri[]): boolean {
    if (files.length >= MAX_SEARCH_FILES) {
        return true;
    }
    files.push(file);
    return false;
}

function isDeniedPathPart(name: string): boolean {
    const normalized = name.toLowerCase();
    return (
        DENIED_DIRECTORY_NAMES.has(normalized) ||
        DENIED_FILE_NAMES.has(normalized) ||
        normalized.startsWith(".env.") ||
        DENIED_FILE_SUFFIXES.some((suffix) => normalized.endsWith(suffix))
    );
}

async function runGit(args: string[]): Promise<{ stdout: string; stderr: string }> {
    const root = workspaceRoot();
    if (root.scheme !== "file") {
        throw new Error("Git tools require a local file Workspace.");
    }
    try {
        const { stdout, stderr } = await execFileAsync("git", ["-C", root.fsPath, ...args], {
            timeout: 10_000,
            maxBuffer: MAX_FILE_BYTES,
            windowsHide: true,
        });
        return { stdout, stderr };
    } catch {
        throw new Error("Git command failed.");
    }
}

function readRequiredString(params: Record<string, unknown>, name: string): string {
    const value = params[name];
    if (typeof value !== "string") {
        throw new Error(`${name} must be a string.`);
    }
    return value;
}

function readOptionalString(params: Record<string, unknown>, name: string, fallback: string): string {
    const value = params[name];
    if (value === undefined) {
        return fallback;
    }
    return readRequiredString(params, name);
}

function fileTypeName(type: vscode.FileType): string {
    if ((type & vscode.FileType.SymbolicLink) !== 0) {
        return "symlink";
    }
    if ((type & vscode.FileType.Directory) !== 0) {
        return "directory";
    }
    return "file";
}

function send(response: ServerResponse, status: number, payload: object): void {
    const body = JSON.stringify(payload);
    response.writeHead(status, {
        "Content-Type": "application/json; charset=utf-8",
        "Content-Length": Buffer.byteLength(body),
    });
    response.end(body);
}

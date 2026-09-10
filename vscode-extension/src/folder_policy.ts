export const CAPABILITIES = ["read", "write", "change", "delete", "exec"] as const;

export type Capability = (typeof CAPABILITIES)[number];

export type FolderRule = {
    path: string;
    permissions: Partial<Record<Capability, boolean>>;
};

export type FolderPolicy = {
    version: 1;
    rules: FolderRule[];
};

export function parseFolderPolicy(source: string): FolderPolicy {
    let parsed: unknown;
    try {
        parsed = JSON.parse(source);
    } catch {
        throw new Error("Folder policy must be valid JSON.");
    }
    if (!isRecord(parsed) || parsed.version !== 1 || !Array.isArray(parsed.rules)) {
        throw new Error("Folder policy must contain version 1 and rules.");
    }

    const paths = new Set<string>();
    const rules = parsed.rules.map((rule) => parseRule(rule, paths));
    if (rules.length === 0) {
        throw new Error("Folder policy must contain at least one rule.");
    }
    return { version: 1, rules };
}

export function allowsFolder(
    policy: FolderPolicy,
    folderPath: string,
    capability: Capability,
): boolean {
    const normalizedFolder = normalizeFolderPath(folderPath);
    const matchingRules = policy.rules
        .filter((rule) => isAncestorOrSame(rule.path, normalizedFolder))
        .sort((left, right) => pathDepth(right.path) - pathDepth(left.path));

    for (const rule of matchingRules) {
        if (Object.hasOwn(rule.permissions, capability)) {
            return rule.permissions[capability] === true;
        }
    }
    return false;
}

function parseRule(value: unknown, paths: Set<string>): FolderRule {
    if (!isRecord(value) || typeof value.path !== "string" || !isRecord(value.permissions)) {
        throw new Error("Each folder rule must contain path and permissions.");
    }
    const path = normalizeFolderPath(value.path);
    if (paths.has(path)) {
        throw new Error("Folder policy cannot contain duplicate paths.");
    }
    paths.add(path);

    const permissions: Partial<Record<Capability, boolean>> = {};
    for (const [capability, allowed] of Object.entries(value.permissions)) {
        if (!CAPABILITIES.includes(capability as Capability) || typeof allowed !== "boolean") {
            throw new Error("Folder policy contains an invalid permission.");
        }
        permissions[capability as Capability] = allowed;
    }
    return { path, permissions };
}

export function normalizeFolderPath(path: string): string {
    if (path === ".") {
        return path;
    }
    if (path.length === 0 || path.startsWith("/") || path.startsWith("\\")) {
        throw new Error("Folder policy paths must be relative directories.");
    }
    const parts = path.split(/[\\/]+/).filter((part) => part.length > 0 && part !== ".");
    if (parts.length === 0 || parts.some((part) => part === "..")) {
        throw new Error("Folder policy paths must be relative directories.");
    }
    return parts.join("/");
}

function isAncestorOrSame(ancestor: string, descendant: string): boolean {
    return ancestor === "." || descendant === ancestor || descendant.startsWith(`${ancestor}/`);
}

function pathDepth(path: string): number {
    return path === "." ? 0 : path.split("/").length;
}

function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}

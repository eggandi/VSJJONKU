# 변경 이력

## 2026-09-11

- Added the first MCP-free Relay path: a private FastAPI command queue and control page, authenticated agent polling in the Workspace Extension, explicit Relay confirmation for destructive commands, startup script, tests, and operator documentation. Public deployment is intentionally not included; the Relay defaults to loopback and requires an HTTPS reverse proxy when exposed.
- Added `browser-extension`, an unpacked Edge/Chrome Action Sender for explicit ChatGPT `[VSJJONKU_EXEC]` JSON blocks. It supports review-before-send by default and optional automatic queueing only for non-destructive existing Workspace methods; changing or deleting always requires local confirmation.
- Clarified README bootstrap ownership: local agents can install and build, while VS Code authentication, OpenAI Tunnel/API-key creation, and ChatGPT MCP app connection remain explicit user-account steps.
- Added managed sibling `JJONKU` junction support in Workspace Bridge version 0.1.6. All ordinary symbolic links remain denied; a policy must name the direct link and its exact sibling target, which is resolved and verified per RPC. The lifecycle script now creates the `Workspace\JJONKU -> ..\JJONKU` junction and defaults its runtime to sibling `Workspace\VSJJONKU`.
- Rewrote README installation around the actual clean-clone flow: Python environment, VSIX package, runtime-local tunnel-client profile, required environment variables, normal lifecycle, and ChatGPT Tool refresh. Reproducible test/build artifacts are already excluded by `.gitignore`.
- Folder policy is now reloaded for every authenticated Bridge RPC, so permission changes apply to the next Tool call after the updated extension is installed. `start-vsjjonku.ps1` now invokes `code-tunnel.exe` directly, preventing `tunnel` and `kill` from being opened as VS Code file arguments.
- Fixed Workspace Extension activation with no folder open. Version 0.1.3 now waits for exactly one Workspace folder and starts the Bridge when that folder is opened, rather than permanently failing during Remote Tunnel connection.
- Simplified Bridge startup in version 0.1.4: the loopback listener starts as soon as the Remote Extension Host is alive, while Workspace-folder and external-policy validation remain enforced for every file RPC. Bridge listen failures are now logged explicitly.
- Hardened lifecycle startup against a conflicting Desktop Remote Tunnel. The script no longer runs global `code-tunnel tunnel kill`; it stops only a previous `vs-jjonku` process and reports a separately active `desktop-...` tunnel.
- Isolated the Remote Extension Host from previously installed personal extensions by using the runtime `bridge-extensions` directory instead of the shared `extensions` directory. The start script installs only the VS쫀쿠 Bridge VSIX there.
- Added destructive `delete_directory(path)` in Extension and MCP Gateway version 0.1.5. It requires `delete` permission on the parent, accepts only an empty non-root directory, and never performs recursive deletion.
- Changed lifecycle defaults so `policy.json` and `session-gate.json` are resolved from the selected runtime directory. For this checkout, the default is the sibling `..\VSJJONKU` directory; no current-directory-relative policy path is used.
- Added `create_directory(path)`, a write-permission Tool that creates exactly one new directory only when its parent already exists. Recursive parent creation and overwriting an existing entry remain disallowed.
- Added `start-vsjjonku.ps1` and `stop-vsjjonku.ps1` to manage the Gateway, VS Code Tunnel, and tunnel-client as one local lifecycle. Process state is stored outside the Workspace and shutdown validates recorded process markers before terminating a process tree.
- Fixed `start-gateway.ps1` absolute-path validation for Windows PowerShell 5.1, which does not provide `[System.IO.Path]::IsPathFullyQualified()`.
- 재현·배포를 위한 Windows 설치 절차를 README에 추가했다. Python Gateway, VSIX 빌드·설치, 외부 정책·세션 게이트, Secure MCP Tunnel, ChatGPT 연결 순서를 한 문서로 정리했다.
- README를 완성품 사용자 안내가 아닌 포크·확장 가능한 기반 프로젝트 안내로 보완했다. Gateway Tool, Extension Bridge RPC, 폴더 정책의 역할과 새 Tool 추가 절차를 기록했다.

## 2026-09-10

- Verified the first real Remote Tunnel cycle with a Desktop VS Code client: Remote Tunnel Workspace -> Workspace Extension Bridge (`/health` HTTP 200) -> local MCP Gateway -> `list_directory(".")` result. Browser embedding inside the Extension Development Host was identified as unsupported and is not part of the operating path.

- Created the private OpenAI Secure MCP Tunnel, installed its official local client, and connected it to the loopback MCP Gateway. The tunnel client initialized the MCP session and its `healthz` and `readyz` endpoints returned HTTP 200.

- Upgraded the Python MCP SDK from v1.30.0 to v2.2.0 and migrated `FastMCP` to `MCPServer`, enabling the required `server/discover` request. Created and connected the `VSJJONKU` ChatGPT developer plugin, then verified a real web ChatGPT `list_directory` call through the Secure MCP Tunnel and Workspace Bridge. Added explicit tool safety annotations and their unit test; the active folder policy remains read-only.

- Added a local session-key expiry gate. An operator configures a 30- or 60-minute lease with a locally entered key; only an `scrypt` hash and salt are stored outside the Workspace. The Gateway watches the lease and exits at expiry. The normal start script requires an external gate file, and unit tests cover renewal, key rejection, and expiry.

- Changed the local session-key gate to require an exactly four-digit numeric key at the operator's request. The gate remains an operational timeout check, not a replacement for the high-entropy Bridge token or OpenAI authentication.

- VS쫀쿠 프로젝트 작업 루트를 초기화하고, 프로젝트 관리 문서 3개를 생성했다.
- Python 기반 Gateway 작업 트리와 패키지 의존성 정의를 추가했다.
- VS Code Remote Tunnel을 Workspace 연결 경로로, VS쫀쿠를 MCP Tool/API 변환 계층으로 구분했다.
- 개발 프로세스를 VS Code 접근 방식 확정 → Wrapper 구현·테스트 → 보안 Gateway 구현으로 확정했다.
- VS Code 접근 방식을 Workspace Extension + loopback Bridge RPC로 확정하고, 일반 SSH와 VS Code Server 내부 프로토콜 의존을 제외했다.
- Python MCP Gateway, Bridge client, VS Code Workspace Extension Bridge의 read-only 최소 구현을 추가했다.
- `list_directory`, `read_file`, `search_code`, `git_status`, `git_diff` Tool 인터페이스를 추가했다.
- Extension Development Host에서 Bridge의 list/read/search와 MCP `search_code` end-to-end 호출을 검증했다. `../` 경로는 거부됨을 확인했다.
- 로컬 검증 절차를 `docs/local-testing.md`에 기록했다. 보안 Gateway와 외부 Tunnel 연결은 다음 단계다.
- 보안 Gateway 단계에서 Gateway loopback 고정, 32자 이상 Bridge token 인증, path traversal·심볼릭 링크·민감 경로 차단을 추가했다.
- 인증 없는 Bridge 요청은 HTTP 401, `.env` MCP read 요청은 차단되는 것을 실제 Extension Development Host에서 검증했다.
- 보안 경계와 미구현 범위를 `docs/security.md`에 기록했다.
- OpenAI Secure MCP Tunnel용 Gateway·tunnel-client 실행 스크립트와 운영 문서를 추가했다. 실제 OpenAI tunnel 연결은 계정의 `tunnel_id`, runtime API key, `tunnel-client` 설치가 필요해 대기 상태다.
- VS Code Workspace Extension의 private VSIX 패키지를 생성했다. Marketplace 배포나 활성 Remote Tunnel 설치는 수행하지 않았다.
- 폴더 단위 `read`·`write`·`change`·`delete`·`exec` 정책 파서와 Bridge read enforcement를 추가했다. 정책 파일은 Workspace 외부 경로만 허용한다.
- `src` 읽기 허용·루트 및 `README.md` 읽기 거부의 Bridge 통합 검증을 수행했다.

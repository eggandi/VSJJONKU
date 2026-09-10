# 변경 이력

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

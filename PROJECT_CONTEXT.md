# VS쫀쿠 프로젝트

## 목적

VS Code Remote Tunnel로 연결한 Workspace를 제한된 MCP Tool로 노출하는 로컬 개발 연동 Gateway를 설계하고 구현한다.

## 작업 범위

- Workspace 내부의 파일 탐색·읽기·코드 검색·Git 상태 확인을 위한 read-only MCP Tool
- VS Code Remote 연동 어댑터와 MCP Gateway의 분리
- 이후 단계에서 명시적 정책을 적용한 write/build/test/exec Tool

## 시작 상태

2026-09-10에 작업 루트가 초기화되었다. VS Code Remote Tunnel을 통한 웹 Workspace 접속은 확인했다.

## 주요 파일

- `AGENTS.md`: 프로젝트 작업 규칙
- `PROJECT_CONTEXT.md`: 프로젝트 상태 및 결정
- `CHANGELOG.md`: 변경 이력
- `pyproject.toml`: Python 패키지 및 의존성 정의
- `src/vsjjonku_gateway/`: Gateway 소스
- `tests/`: 검증 코드

## 확정된 결론 및 결정 이력

- 작업 루트: `C:\workspace\onedrive\Research\JJONKU`
- 구현 언어: Python 3.12 이상
- MCP 서버 SDK: Python `mcp` 패키지
- VS Code Remote Tunnel은 Workspace 연결 경로이고, VS쫀쿠 Gateway가 MCP Tool/API 변환 계층이다.
- 개발 순서: 1) VS Code 접근 방식 확정, 2) Wrapper 구현·테스트, 3) 보안 Gateway 구현.
- VS Code 접근 방식: `extensionKind: ["workspace"]`인 VS Code Workspace Extension. Gateway는 loopback Bridge RPC로 Extension에 요청한다.
- SSH는 VS Code Remote Tunnel의 외부 제어 인터페이스로 사용하지 않는다.

## 검토 중인 내용 및 미결 쟁점

- OpenAI Secure MCP Tunnel client is connected and healthy. The `VSJJONKU` ChatGPT developer plugin is created and connected without application authentication.

## 다음 작업

1. Workspace Extension과 loopback Bridge 기반 read-only Wrapper 구현 및 로컬 검증을 완료했다.
2. Workspace 경계·민감 파일 접근·Bridge 인증을 갖춘 보안 Gateway 구현 및 로컬 검증을 완료했다.
3. ChatGPT custom plugin에서 등록된 Secure Tunnel을 선택하고 도구 스캔 및 첫 read-only 호출을 검증한다.

## 현재 구현 상태

- Python MCP Gateway: `src/vsjjonku_gateway/server.py`
- The gateway uses MCP Python SDK v2.2.0, which implements the modern `server/discover` request required by ChatGPT Secure MCP Tunnel discovery.
- Verified 2026-09-10: web ChatGPT called `list_directory` through the connected `VSJJONKU` plugin and received the JJONKU Workspace directory listing. Folder capability enforcement is in the Workspace Extension; the selected external policy is reloaded for each authenticated RPC from extension version 0.1.2 onward.
- MCP annotations distinguish read-only, create-only, and destructive Workspace actions; the active policy, not the model, remains the enforcement boundary.
- A locally renewed session-key gate is implemented. The normal gateway start script now requires an external gate configuration and terminates the Gateway when its 30- or 60-minute lease expires. The key is exactly four digits and serves only as a local operating check; it is not a substitute for high-entropy transport or Bridge credentials. It has not been activated for the already-running Gateway because its user-selected key has not yet been configured.
- Verified 2026-09-10: a Desktop VS Code Remote - Tunnels client opened the JJONKU Workspace, activated the loopback Bridge, and the local MCP Gateway successfully called `list_directory(".")` end-to-end.
- Gateway Bridge client: `src/vsjjonku_gateway/bridge_client.py`
- Workspace Extension Bridge: `vscode-extension/src/extension.ts`
- 제공 Tool: `list_directory`, `read_file`, `search_code`, `git_status`, `git_diff`, `write_file`, `create_directory`, `change_file`, `delete_file`, `delete_directory`
- 2026-09-10 로컬 검증에서 Extension Development Host와 MCP `search_code` 호출까지 성공했다.
- 민감 파일·심볼릭 링크·경로 이탈 차단과 Bridge Bearer token 인증을 구현했다. 정책 상세는 `docs/security.md`에 기록한다.
- 폴더 단위 권한 정책을 구현했다. 정책은 Workspace 외부 파일에서 로드하며, `read`·`write`·`change`·`delete`가 각 Tool에 적용된다. `exec`는 아직 노출하지 않았다.
- OpenAI Secure MCP Tunnel의 `tunnel-client`가 로컬 MCP endpoint에 연결되었고 `/healthz`, `/readyz`가 HTTP 200을 반환했다. ChatGPT app-level tool call은 아직 검증하지 않았다.
- Workspace Extension VSIX 패키지는 `vscode-extension/vsjjonku-workspace-bridge-0.1.4.vsix`까지 빌드되어 있다. 이 버전은 Remote Extension Host가 시작되면 Bridge를 먼저 열고, 각 Tool 호출 때 정확히 하나의 Workspace 폴더와 외부 정책을 검사한다. 새 버전은 다음 VS Code Tunnel 시작 시 설치된다.
- `scripts/start-vsjjonku.ps1`와 `scripts/stop-vsjjonku.ps1`는 Gateway, VS Code Tunnel, tunnel-client의 일상 시작·종료를 하나의 명령으로 묶는다. 기본 정책·세션 게이트 파일은 선택된 런타임 폴더에 둔다. 이 체크아웃에서는 기존 sibling runtime이 있으므로 `C:\workspace\onedrive\Research\VSJJONKU`가 기본값이다.
- VS쫀쿠용 `vs-jjonku` Tunnel과 VS Code Desktop의 별도 `desktop-...` Remote Tunnel은 동시에 사용하지 않는다. 시작 스크립트는 다른 Tunnel을 전역 종료하지 않고 충돌을 오류로 표시한다.
- Remote Extension Host는 런타임의 `bridge-extensions`를 전용 확장 폴더로 사용한다. 이전 개인 확장과 VS쫀쿠 Bridge의 호환성·수명 문제를 분리하기 위한 조치다.
- Version 0.1.6 supports the intended sibling layout: `workspace\JJONKU` is source, `workspace\VSJJONKU` is RuntimeRoot, and a remotely opened sibling project receives a `JJONKU -> ..\JJONKU` managed junction. The external policy must declare that exact link. Every RPC resolves and validates its target; all other links remain denied.
- 배포 저장소에는 `.venv`, `node_modules`, Extension 컴파일 결과물과 VSIX를 포함하지 않는다. `README.md`의 clean-clone 설치 절차가 이들을 재생성하며, OpenAI `tunnel-client`와 its profile은 Workspace 외부 RuntimeRoot에 둔다.

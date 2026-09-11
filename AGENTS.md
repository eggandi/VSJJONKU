# JJONKU 작업 규칙

- 구현은 한 번에 전체 시스템을 만들지 않고, 검증 가능한 최소 단위로 진행한다.
- 작업 순서는 다음을 따른다: VS Code 접근 방식 확정 → Wrapper 구현·테스트 → 보안 Gateway 구현.
- VS Code 접근 방식은 SSH 또는 VS Code 확장 연동 후보를 검증한 뒤 확정한다.
- 초기 Wrapper는 read-only Workspace Tool을 우선 구현한다.
- VS Code 접근에는 public VS Code Extension API를 사용한다. Remote Tunnel의 내부 SSH 프로토콜이나 비공개 VS Code Server 프로토콜에 의존하지 않는다.
- VS Code 확장은 Workspace Extension으로 실행하며, Gateway와의 Bridge는 loopback으로만 수신한다.
- Wrapper 검증은 Extension Development Host와 loopback Bridge를 사용한다. 외부 노출과 인증·민감 파일 정책은 보안 Gateway 단계에서 추가한다.
- MCP Gateway는 loopback에만 바인딩한다. OpenAI Secure MCP Tunnel은 외부 transport로만 사용하며, API key·tunnel ID·Bridge token은 저장소에 기록하지 않는다.
- Agent 권한은 폴더 단위 `read`·`write`·`change`·`delete`·`exec` 정책으로 제한한다. 파일별 허용 규칙은 만들지 않으며, 민감 파일은 고정 차단한다.
- 로컬 Relay 경로를 기본 작업 방향으로 둔다. OpenAI Secure MCP Tunnel과 VS Code Remote Tunnel은 외부 접근이 필요한 선택 경로로 유지하며, 로컬 Relay 기본 경로에 의존성을 추가하지 않는다.
- WebGPT와 Local CLI는 별도 Agent 진입점이다. WebGPT는 브라우저 확장이 명시적 실행안을 Relay에 전달하고, Local CLI는 Relay API를 직접 호출한다. Relay는 LLM 판단을 수행하지 않는 인증·큐·결과 전달 계층이다.
- 자동화 권한은 명령 자동 큐잉과 WebGPT 결과 자동 왕복을 분리한다. `change`·`delete` 권한과 로컬 확인은 자동 왕복 설정으로 우회하지 않는다.
- WebGPT 읽기는 만료형 read-only capability URL을 가진 별도 Web Portal로 제공하는 방안을 사용한다. 쓰기 권한은 Portal URL에 넣지 않고, 브라우저 확장이 명시적 실행안만 Relay로 복사·전달하는 경로로 한정한다.
- 로컬 모델 연결은 loopback OpenAI-compatible endpoint만 허용한다. 모델 파일 자동 다운로드, 외부 모델 endpoint, 저장소 내 token 저장은 추가하지 않는다.
- 상위 작업 영역 규칙은 `C:\workspace\onedrive\Research\AGENTS.md`를 따른다.

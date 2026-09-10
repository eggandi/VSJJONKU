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
- 상위 작업 영역 규칙은 `C:\workspace\onedrive\Research\AGENTS.md`를 따른다.

# 자체 Web Relay (MVP)

이 Relay는 MCP 없이 자체 웹페이지에서 VSJJONKU Workspace Extension으로 명령을 전달하는 최소 구현이다. ChatGPT 웹은 작업안을 생성하고, [브라우저 확장](../browser-extension/README.md)이 명시적으로 태그된 JSON만 Relay로 전달할 수 있다.

```text
Relay 웹페이지 -> Relay 작업 큐 <- Workspace Extension outbound polling
                                      -> VS Code Workspace API
```

## 경계

- Relay는 명령을 해석하거나 LLM 호출을 하지 않는다.
- Extension은 기존 Workspace 정책, 민감 경로 차단, managed `JJONKU` link 검증을 그대로 적용한다.
- `change_file`, `delete_file`, `delete_directory`는 Relay API에서도 `confirm: true`가 필요하다.
- Relay는 메모리 큐다. 재시작하면 대기·완료 명령 이력은 사라진다.
- 공개 운영은 HTTPS reverse proxy 뒤에서만 한다. 기본 bind는 `127.0.0.1:8787`이다.
- 브라우저 확장의 자동 큐잉은 읽기·생성 명령에만 적용한다. 변경·삭제는 항상 사용자가 확인한다.
- Relay는 명령을 poll한 뒤 Extension의 결과를 기다린다. Extension이 poll 직후 비정상 종료하면 그 명령은 재시도되지 않는다. 이 MVP에는 영속 큐·재전송이 없다.

## 로컬 검증

별도 PowerShell에서 Relay token 두 개를 설정하고 실행한다.

```powershell
$env:VSJJONKU_RELAY_WEB_TOKEN = "<32자-이상-웹-토큰>"
$env:VSJJONKU_RELAY_AGENT_TOKEN = "<32자-이상-에이전트-토큰>"
$gate = "C:\path\outside-workspace\session-gate.json"
.\scripts\start-relay.ps1 -SessionGatePath $gate
```

`http://127.0.0.1:8787/`에서 명령을 큐에 넣을 수 있다.

VS Code Tunnel을 시작하는 같은 PowerShell에는 아래도 설정한다. 개발 Relay는 loopback HTTP를 허용하지만, 외부 Relay는 반드시 HTTPS URL을 사용한다.

```powershell
$env:VSJJONKU_RELAY_URL = "http://127.0.0.1:8787"
$env:VSJJONKU_RELAY_AGENT_ID = "default"
$env:VSJJONKU_RELAY_AGENT_TOKEN = "<위와-동일한-에이전트-토큰>"
& .\scripts\start-vsjjonku.ps1
```

Remote Extension Host가 시작되면 Relay를 20초 long-poll하며, 받은 명령의 실행 결과를 같은 request ID로 반환한다.

## ChatGPT 웹 반자동 전달

`browser-extension`을 Edge/Chrome 개발자 모드에서 압축 해제 확장으로 설치한다. Relay URL, Agent ID, web token을 저장한 뒤 ChatGPT 응답에서 아래 블록을 선택하면 팝업의 대기 작업으로 들어간다.

````text
[VSJJONKU_EXEC]
```json
{"method":"search_code","params":{"query":"epoll_wait","path":"."}}
```
````

`안전한 읽기/생성 명령 자동 큐잉`을 켜도 `change_file`, `delete_file`, `delete_directory`는 Relay에 보내기 전에 팝업에서 체크해야 한다. 확장은 전체 대화·쿠키·Remote Tunnel 페이지를 읽거나 제어하지 않는다.

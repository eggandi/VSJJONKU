# VS쫀쿠 접근 구조

## 확정된 접근 방식

VS Code Workspace Extension을 사용한다. 확장은 `extensionKind: ["workspace"]`로 선언하고, VS Code Remote Tunnel이 연결한 원격 Extension Host에서 실행한다.

```text
ChatGPT MCP
  → VS쫀쿠 Python Gateway
  → loopback Bridge RPC
  → VS쫀쿠 VS Code Workspace Extension
  → VS Code Workspace
```

## 선택 이유

- Workspace Extension은 Workspace가 있는 머신에서 실행되며 VS Code Extension API로 파일·검색·명령 작업에 접근한다.
- VS Code Remote Tunnel의 SSH 연결은 VS Code 클라이언트 전용 내부 연결이다. VS쫀쿠의 일반 SSH endpoint로 사용하지 않는다.
- Gateway와 Extension 사이 Bridge는 loopback으로만 수신한다. 외부 공개와 인증은 이후 보안 Gateway 단계에서 처리한다.

## 1차 Tool 범위

- `list_directory`
- `read_file`
- `search_code`
- `git_status`
- `git_diff`

쓰기·빌드·테스트·임의 명령 실행은 1차 범위에서 제외한다.


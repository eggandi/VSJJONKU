# 로컬 Relay와 Hermes 테스트 Agent

로컬 Relay는 OpenAI 계정·Secure MCP Tunnel·VS Code Remote Tunnel 없이 같은 PC에서 Workspace Extension을 실행한다.

```text
Hermes 로컬 모델 -> local-agent CLI -> Local Relay -> VS Code Workspace Extension -> Workspace
```

`local-agent`는 자연어를 명령으로 바꾸는 선택 계층이다. 실제 `list_directory`, `read_file`, `search_code`, `write_file`, `change_file`, `delete_file` 실행은 Relay를 거쳐 Workspace Extension이 한다.

## 모델

초기 테스트 모델 ID는 `NousResearch/Hermes-3-Llama-3.2-3B`다. 이 모델은 JSON·function calling 형식 테스트용이며, 복잡한 코딩 작업의 기본 모델 성능은 보장하지 않는다. LM Studio 또는 llama.cpp의 loopback OpenAI-compatible API를 사용한다.

- 모델: <https://huggingface.co/NousResearch/Hermes-3-Llama-3.2-3B>
- 공식 GGUF: <https://huggingface.co/NousResearch/Hermes-3-Llama-3.2-3B-GGUF>

모델 파일은 자동 다운로드하지 않는다. 기본 endpoint는 `http://127.0.0.1:1234/v1`이고, 다른 endpoint·model ID는 `run-local-agent.ps1` 인자로 바꾼다.

## 시작

VSIX를 먼저 빌드한 뒤 작업 폴더에서 시작한다.

```powershell
Push-Location C:\path\to\JJONKU\vscode-extension
npm ci
npm run compile
npx --yes @vscode/vsce package --allow-missing-repository
Pop-Location

& C:\path\to\JJONKU\scripts\start-local-relay.ps1
```

첫 실행은 4자리 session key를 설정한다. 스크립트는 별도 로컬 VS Code profile 창을 열며, 여기서 대상 Workspace를 Trust해야 Extension이 Relay poll을 시작한다. RuntimeRoot에는 같은 Windows 사용자만 복호화할 수 있는 DPAPI token 설정이 저장된다.

## 모델 Agent 실행

```powershell
& C:\path\to\JJONKU\scripts\run-local-agent.ps1 `
  -Task "README를 읽고 구조를 설명해줘"
```

변경·삭제 명령은 로컬 콘솔에서 별도 `y` 확인이 필요하다. 모델 endpoint와 Relay endpoint는 `127.0.0.1`/`localhost`만 허용한다.

## 종료

```powershell
& C:\path\to\JJONKU\scripts\stop-local-relay.ps1
```

Relay만 종료한다. 열린 VS Code 창은 사용자가 계속 사용하거나 직접 닫는다.

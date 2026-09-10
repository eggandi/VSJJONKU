# VS쫀쿠

VS쫀쿠는 웹 ChatGPT가 VS Code에서 열어둔 로컬 Workspace를 제한된 MCP Tool로 다룰 수 있게 하는 로컬 제어 계층이다. 완성된 서비스가 아니라, 각 개발자가 포크해 자기 프로젝트용 Tool·정책·명령을 추가하는 오픈소스 기반 프로젝트다.

```text
ChatGPT → OpenAI Secure MCP Tunnel → local tunnel-client
        → VS쫀쿠 Gateway → VS Code Workspace Extension → Workspace
```

현재 제공 Tool은 `list_directory`, `read_file`, `search_code`, `git_status`, `git_diff`, `write_file`, `create_directory`, `change_file`, `delete_file`, `delete_directory`다. `delete_directory`는 비어 있는 폴더만 삭제하며 재귀 삭제와 Workspace 루트 삭제는 지원하지 않는다. `exec`, `build`, `test`는 다음 구현 단계다.

## 이 저장소를 가져가서 커스텀하기

GitHub에서 **Fork**하거나 Template으로 새 저장소를 만든 뒤 사용한다. 배포자는 자신의 저장소 이름, VS Code Extension publisher, OpenAI Tunnel, 정책 파일을 사용한다. 이 저장소의 `VSJJONKU` Tunnel·Bridge token·정책 파일은 공유 대상이 아니다.

커스텀 가능한 경계는 다음과 같다.

| 변경 지점 | 역할 |
| --- | --- |
| `src/vsjjonku_gateway/server.py` | ChatGPT에 노출할 MCP Tool 이름·설명·입력 정의 |
| `vscode-extension/src/extension.ts` | Tool 호출을 받아 Workspace API 또는 제한된 로컬 작업으로 수행 |
| `vscode-extension/src/folder_policy.ts` | `read`·`write`·`change`·`delete`·`exec` 폴더 권한 해석 |
| `config/vsjjonku-folder-policy.example.json` | 사용자별 허용 폴더와 권한 예시 |
| `scripts/` | Gateway와 Tunnel의 실행 방식 |

새 Tool은 Gateway와 Extension 양쪽에 한 쌍으로 추가해야 한다. 예를 들어 `project_info`를 추가할 때는 다음 순서를 따른다.

1. `server.py`에 `@server.tool` 함수와 설명을 추가한다.
2. 같은 이름의 Bridge RPC를 `extension.ts`의 `dispatch()`에 등록하고, 입력 검증·경로 검증·권한 검사를 한 뒤 구현한다.
3. 파일 변경이나 명령 실행이면 해당 폴더의 `change` 또는 `exec` 권한을 먼저 확인한다.
4. Python 단위 테스트와 Extension 테스트를 추가한다.
5. `npm run compile` 후 VSIX를 다시 패키징·설치하고 Gateway를 재시작한다.

`exec`는 현재 의도적으로 미구현이다. 추가한다면 범용 shell을 그대로 노출하지 말고, 허용한 실행 파일·인자·작업 폴더·timeout을 명시하는 allowlist로 구현해야 한다.

## 설치·실행 (포크한 저장소 기준, Windows)

### 처음 한 번 설치

이 저장소에는 Python 가상환경, `node_modules`, 컴파일 결과물, VSIX, Tunnel credential를 넣지 않는다. 아래 설치를 한 번 실행한다.

```powershell
git clone <저장소-URL>
cd JJONKU

py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"

Push-Location .\vscode-extension
npm ci
npm run compile
npx --yes @vscode/vsce package --allow-missing-repository
Pop-Location
```

### 사용자 인증이 필요한 단계

Codex CLI 같은 로컬 Agent는 위 설치와 이후 스크립트 실행을 자동화할 수 있다. 다만 다음 인증·계정 작업은 사용자 계정에서 한 번 직접 처리해야 한다.

1. VS Code에서 GitHub 또는 Microsoft 계정으로 로그인하고 VS Code Remote Tunnel 사용을 승인한다.
2. OpenAI Platform에서 Secure MCP Tunnel을 만들고, `Tunnels Read + Use` runtime API key를 만든다.
3. ChatGPT 개발자 모드에서 개인 MCP 앱을 만들고 해당 Secure MCP Tunnel을 연결한다.

토큰·API key·로그인 세션은 저장소에 넣지 않는다. Agent에게 설치를 맡길 때는 “README의 처음 한 번 설치를 실행하고, 사용자 인증이 필요한 단계에서 멈춰라”라고 지시하면 된다.

OpenAI Platform에서 Secure MCP Tunnel을 하나 만들고, `Tunnels Read + Use` 권한만 가진 runtime API key를 만든다. `JJONKU` 저장소와 작업 폴더를 같은 `workspace` 폴더에 둔다. Platform에서 받은 공식 Windows `tunnel-client` 압축을 아래 런타임 폴더에 풀고 프로필을 만든다.

```text
workspace\
  JJONKU\       <- 이 저장소
  VSJJONKU\     <- 정책·세션·Tunnel runtime
  MyProject\    <- Remote로 여는 작업 폴더
```

```powershell
$runtime = Join-Path (Split-Path -Parent (Get-Location)) "VSJJONKU"
New-Item -ItemType Directory -Force "$runtime\tunnel-client", "$runtime\tunnel-client-profile" | Out-Null
# Platform에서 받은 tunnel-client-windows-amd64.zip의 내용을 $runtime\tunnel-client 에 압축 해제한다.

$env:CONTROL_PLANE_API_KEY = "<OpenAI-runtime-API-key>"
$env:VSJJONKU_TUNNEL_ID = "tunnel_..."
& "$runtime\tunnel-client\tunnel-client.exe" init `
  --profile vsjjonku `
  --profile-dir "$runtime\tunnel-client-profile" `
  --tunnel-id $env:VSJJONKU_TUNNEL_ID `
  --mcp-server-url "http://127.0.0.1:8000/mcp" `
  --health-listen-addr "127.0.0.1:8091"
```

새 PowerShell 창마다 아래 두 환경 변수를 다시 설정한다. `VSJJONKU_BRIDGE_TOKEN`은 임의의 32자 이상 고난도 문자열이며, Gateway·Workspace Bridge가 같은 값으로 인증하는 데 쓴다.

```powershell
$env:VSJJONKU_BRIDGE_TOKEN = "<32자-이상-랜덤-문자열>"
$env:CONTROL_PLANE_API_KEY = "<OpenAI-runtime-API-key>"
```

### 평소 시작·종료

설치가 끝난 뒤에는 `workspace\MyProject`처럼 **JJONKU와 같은 부모를 공유하는 작업 폴더**에서 아래 한 명령으로 Gateway·VS Code Tunnel·tunnel-client를 함께 실행한다. 스크립트는 `MyProject\JJONKU` Junction을 자동 생성한다. 이 링크는 중앙 `workspace\JJONKU`를 가리키므로, Tool로 `JJONKU/...`를 수정하면 원본에 즉시 반영된다.

```powershell
& C:\path\to\JJONKU\scripts\start-vsjjonku.ps1
```

첫 실행 또는 lease 만료 뒤에는 로컬 네 자리 세션 키를 묻는다. 이후 출력된 주소를 데스크톱 VS Code의 Remote Tunnel 연결로 열고, **동일한 대상 Workspace 폴더**를 열어 Trust한다. 종료는 아래 명령이 시작 스크립트가 만든 프로세스만 PID 기준으로 종료한다.

```powershell
& C:\path\to\JJONKU\scripts\stop-vsjjonku.ps1
```

기본 런타임 위치는 프로젝트와 같은 상위 폴더의 `VSJJONKU`다. `policy.json`과 `session-gate.json`도 기본적으로 이 런타임 폴더에 둔다. 작업 폴더가 아닌 그 형제 폴더에 있으므로 정책 파일은 Remote Workspace 밖에 유지된다. 다른 위치를 쓰려면 두 스크립트에 같은 `-RuntimeRoot`를 지정한다.

VS쫀쿠 실행 중에는 같은 PC에서 VS Code의 **Remote Tunnel Access 켜기**로 별도 Tunnel을 만들지 않는다. `code-tunnel`은 한 호스트 Tunnel만 관리하므로, `desktop-...` 같은 다른 Tunnel이 이미 연결되어 있으면 시작 스크립트가 중단하고 이름을 표시한다.

시작 스크립트는 런타임의 `bridge-extensions` 폴더만 Remote Extension Host에 제공한다. 개인 VS Code 확장이나 Codex·Copilot 확장과 Bridge 실행 환경을 분리하기 위한 것이며, 이 폴더에는 VS쫀쿠 Workspace Bridge VSIX만 자동 설치된다.

### ChatGPT 앱 갱신

Gateway Tool을 추가·변경한 경우에는 VSIX를 다시 패키징한 뒤 VS쫀쿠를 재시작한다. ChatGPT의 개인 MCP 앱에서도 **새로고침/Refresh**로 Tool 목록을 다시 스캔하고, 새 대화에서 테스트한다. 앱이 Refresh를 제공하지 않거나 갱신이 실패하면 기존 개인 앱을 삭제하고 같은 Secure MCP Tunnel로 새 앱을 만든다.

### 수동 설치 참고

위의 처음 한 번 설치가 표준 절차다. 아래 내용은 Gateway·Extension·Tunnel을 각각 수동 실행해야 할 때만 참고한다.

### 1. 준비물

- Git
- Python 3.12 이상
- Node.js LTS 및 npm
- VS Code 1.137 이상과 VS Code Remote Tunnel
- OpenAI Platform의 Secure MCP Tunnel 및 공식 `tunnel-client`

### 2. 저장소와 Python Gateway 설치

```powershell
git clone <저장소-URL>
cd JJONKU

py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

설치 확인:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

### 3. Workspace 권한 정책 만들기

정책과 세션 파일은 **Workspace 밖**에 둔다. 아래 예시는 `D:\VSJJONKU`를 사용한다.

```powershell
New-Item -ItemType Directory -Force D:\VSJJONKU
Copy-Item .\config\vsjjonku-folder-policy.example.json D:\VSJJONKU\policy.json
$env:VSJJONKU_POLICY_PATH = "D:\VSJJONKU\policy.json"
```

처음에는 `read`만 허용한 채 `list_directory`와 `search_code`부터 확인한다. `write`, `change`, `delete`는 필요한 폴더에만 명시적으로 연다. 기본 예시의 `managedLinks`는 `MyProject\JJONKU -> ..\JJONKU`만 허용한다. 다른 링크와 `.env`, SSH key 같은 민감 파일은 정책과 무관하게 차단된다.

### 4. VS Code Workspace Extension 설치

```powershell
Push-Location .\vscode-extension
npm ci
npm run compile
npx --yes @vscode/vsce package --allow-missing-repository
Pop-Location
```

생성된 `vscode-extension\vsjjonku-workspace-bridge-*.vsix`를 **Remote Tunnel이 연결한 VS Code의 Workspace Extension Host**에 설치한다. VS Code 명령 팔레트에서 `Extensions: Install from VSIX...`를 선택해 설치할 수 있다.

Bridge token은 32자 이상의 랜덤 문자열로 만들고, VS Code Remote Tunnel을 실행하는 프로세스 환경에 넣는다. 이미 Tunnel을 실행 중이면 종료 후 같은 환경에서 다시 시작해야 한다.

```powershell
$env:VSJJONKU_BRIDGE_TOKEN = "<32자-이상-랜덤-토큰>"
code tunnel
```

VS Code에서 대상 Workspace를 열고 Workspace Trust를 허용한다.

### 5. 세션 게이트와 Gateway 실행

다른 터미널에서 동일한 Bridge token과 정책 경로를 설정한다.

```powershell
cd JJONKU
$env:VSJJONKU_BRIDGE_TOKEN = "<위와-동일한-토큰>"
$env:VSJJONKU_POLICY_PATH = "D:\VSJJONKU\policy.json"

$gate = "D:\VSJJONKU\session-gate.json"
.\.venv\Scripts\python.exe -m vsjjonku_gateway.session_gate configure --path $gate --minutes 30
.\scripts\start-gateway.ps1 -McpPort 8000 -SessionGatePath $gate
```

`configure`는 로컬 콘솔에서 정확히 네 자리 숫자 키를 두 번 받는다. 키는 ChatGPT나 터널로 전달되지 않는다. 30분 또는 60분마다 아래 명령으로 연장한다.

```powershell
.\.venv\Scripts\python.exe -m vsjjonku_gateway.session_gate renew --path $gate
```

### 6. OpenAI Secure MCP Tunnel 연결

OpenAI Platform에서 Tunnel을 만들고, runtime API key에는 최소 `Tunnels Read + Use`만 부여한다. 두 값은 저장소나 정책 파일에 쓰지 않는다.

```powershell
$env:VSJJONKU_TUNNEL_ID = "tunnel_..."
$env:CONTROL_PLANE_API_KEY = "sk-..."

.\scripts\setup-openai-tunnel.ps1 -McpPort 8000
.\scripts\run-openai-tunnel.ps1
```

ChatGPT 개발자 모드에서 개인 앱을 만들고 Connection type을 **Tunnel**로 선택한 뒤, 해당 Tunnel을 연결한다. 처음에는 `list_directory`만 호출해 경로가 맞는지 확인한다.

## 운영 주의사항

- `.env`, API key, Bridge token, Tunnel ID, `session-gate.json`, `policy.json`은 커밋하지 않는다.
- Gateway와 Bridge는 `127.0.0.1`만 수신한다. 외부 접근은 Secure MCP Tunnel만 사용한다.
- Gateway를 종료하거나 세션 lease가 만료되면 ChatGPT 도구 호출도 중단된다.
- 의존성을 지운 뒤에는 2단계의 가상환경 생성·설치를 다시 실행하면 된다.

## 작업 트리

```text
src/vsjjonku_gateway/       Python MCP Gateway
vscode-extension/           Workspace Extension Bridge
config/                      비밀값을 제외한 정책 예시
scripts/                     Gateway 및 Tunnel 실행 스크립트
docs/                        설계·보안·점검 문서
tests/                       단위·통합 테스트
```

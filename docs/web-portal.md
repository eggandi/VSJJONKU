# WebGPT 읽기 전용 Portal

WebGPT가 VS Code Remote Tunnel 로그인 세션을 직접 승계할 수는 없다. 이 Portal은 정책이 허용한 Workspace 파일을 별도 HTTPS 읽기 페이지로 제공해, WebGPT가 일반 웹페이지처럼 폴더와 파일 링크를 열어 보게 하는 경로다.

```text
WebGPT -> HTTPS capability URL -> Local Relay -> VS Code Workspace Extension -> Workspace
```

Portal은 `list_directory`와 `read_file`만 Relay 작업 큐에 넣는다. `write_file`, `change_file`, `delete_file`, `delete_directory`, `exec`는 Portal에 존재하지 않는다.

## 보안 모델

- Portal URL은 암호화된 경로가 아니라 256비트 무작위 bearer capability다.
- 각 capability는 1~60분 TTL과 최대 200개 HTTP 요청으로 제한되며 Relay 재시작 시 즉시 사라진다.
- 응답은 `Cache-Control: no-store`, `Referrer-Policy: no-referrer`, `noindex`, CSP를 사용한다.
- 실제 경로·민감 파일·폴더 권한 검사는 Workspace Extension이 다시 수행한다.
- URL을 가진 사람은 만료 전까지 읽을 수 있다. ChatGPT 대화·스크린샷·공유 문서에 URL을 불필요하게 남기지 않는다.
- 공개 배포는 HTTPS reverse proxy 또는 사용자가 통제하는 HTTPS tunnel 뒤에서만 한다. Relay 자체는 `127.0.0.1`에만 바인딩한다.

## Portal 생성

Local Relay가 실행 중이고 Workspace Extension이 `default` agent ID로 poll 중인 상태에서 실행한다.

```powershell
& C:\path\to\JJONKU\scripts\new-read-portal.ps1 -Minutes 15
```

개발 중에는 `http://127.0.0.1:8787/r/.../` URL이 출력된다. OpenAI가 읽을 URL을 만들려면 동일 Relay를 외부에 HTTPS로 publish한 뒤 public origin을 지정한다.

```powershell
& C:\path\to\JJONKU\scripts\new-read-portal.ps1 `
  -Minutes 15 `
  -PublicBaseUrl "https://portal.example"
```

이 스크립트는 public tunnel을 만들지 않는다. 사용자가 이미 운영하는 HTTPS reverse proxy 또는 tunnel이 loopback Relay로 전달해야 한다.

## WebGPT 사용 방식

출력된 root URL을 WebGPT 대화에 제공하면, WebGPT는 Portal의 폴더 링크와 파일 링크를 일반 웹페이지처럼 읽을 수 있다. 새 Portal은 새 capability URL을 만들며, 이전 URL의 TTL을 연장하지 않는다.

Portal은 읽기 전용이다. WebGPT가 파일 변경을 원하면 브라우저 확장의 `[VSJJONKU_EXEC]` 실행안 → Relay → Workspace Extension 경로를 사용한다.

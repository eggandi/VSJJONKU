# VS쫀쿠

VS Code Remote Tunnel이 연결한 Workspace를 제한된 MCP Tool로 노출하는 로컬 Gateway다.

초기 구현은 read-only Tool(`list_directory`, `read_file`, `search_code`, `git_status`, `git_diff`)부터 시작한다. 쓰기·빌드·테스트·명령 실행은 별도 정책과 검증 이후 추가한다.

## 작업 트리

```text
src/vsjjonku_gateway/       Gateway 구현
  tools/                    MCP Tool 정의
  transports/               VS Code Remote 연동 어댑터
tests/                      단위·통합 테스트
config/                     비밀값을 제외한 예시 설정
scripts/                    로컬 실행 및 점검 스크립트
docs/                       설계 및 운영 문서
```


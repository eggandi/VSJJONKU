# VSJJONKU Action Sender

ChatGPT 웹 응답의 명시적 `VSJJONKU_EXEC` 블록만 VSJJONKU Relay 작업 큐로 보낸다. ChatGPT 탭을 원격 제어하거나 전체 대화를 수집하지 않는다.

## 설치

1. Edge 또는 Chrome의 확장 관리 페이지를 열고 **개발자 모드**를 켠다.
2. **압축해제된 확장 로드**를 누른 뒤 이 `browser-extension` 폴더를 선택한다.
3. 확장 아이콘을 열어 Relay URL, Agent ID, Relay web token을 저장한다.
   로컬 기본 Relay URL은 `http://127.0.0.1:8787`이다.

외부 Relay에는 HTTPS URL만 사용할 수 있다. `127.0.0.1` 및 `localhost`만 HTTP 개발 연결을 허용한다.

## 사용

ChatGPT에 아래 형식으로만 실행안을 출력하도록 요청한다.

````text
[VSJJONKU_EXEC]
```json
{"method":"list_directory","params":{"path":"."}}
```
````

응답에서 해당 블록을 드래그 선택하면 확장이 작업을 대기 목록에 넣는다. 확장 팝업에서 내용을 확인한 뒤 **Relay로 보내기**를 누른다.

`안전한 읽기/생성 명령 자동 큐잉`을 켜면 새로 나타난 태그 블록 중 읽기·생성 명령만 자동으로 큐잉한다. `change_file`, `delete_file`, `delete_directory`는 항상 수동 확인이 필요하다.

Relay는 기존 VSJJONKU Workspace 명령만 받는다.

- `list_directory`, `read_file`, `search_code`, `git_status`, `git_diff`
- `write_file`, `create_directory`, `change_file`, `delete_file`, `delete_directory`

`exec`, `build`, `test`는 이 MVP에 노출하지 않는다.

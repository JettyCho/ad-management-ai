---
name: slack-manage
description: Slack API를 curl로 직접 호출하여 메시지 전송, 채널 조회, 검색, 파일 업로드 등을 수행합니다. User Token(xoxp-)을 사용하여 사용자 본인 이름으로 동작합니다. TRIGGER when: 사용자가 슬랙 메시지 보내기, 채널 관리, 파일 공유, 리액션, 검색 등 슬랙 조작을 요청할 때. "슬랙에 보내줘", "슬랙 메시지", "채널에 올려줘", "슬랙 검색", "DM 보내줘" 등 슬랙 액션 키워드가 포함될 때 사용.
argument-hint: (자연어로 슬랙 작업을 자유롭게 입력)
disable-model-invocation: false
context: compress
allowed-tools: Bash, Read, Grep, Glob
---

# Slack 관리 (curl + Slack Web API)

## 환경 설정

`.env` 파일에서 `SLACK_USER_TOKEN`을 읽어 사용한다.
User Token(`xoxp-`)을 사용하므로 모든 API 호출은 **사용자 본인 이름**으로 실행된다.

```bash
source .env
```

---

## 명령 실행 방식

모든 Slack API 호출은 curl로 직접 수행한다:

```bash
curl -s -X POST https://slack.com/api/{method} \
  -H "Authorization: Bearer $SLACK_USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{...}' | python3 -m json.tool
```

---

## 채널 ID 조회

Slack API는 채널명이 아닌 **채널 ID**를 사용한다. 채널명으로 ID를 찾는 방법:

```bash
# 채널 목록에서 검색
curl -s "https://slack.com/api/conversations.list?types=public_channel,private_channel&limit=1000" \
  -H "Authorization: Bearer $SLACK_USER_TOKEN" \
  | python3 -c "
import json, sys
data = json.load(sys.stdin)
for ch in data.get('channels', []):
    if '검색어' in ch['name']:
        print(f\"{ch['id']} #{ch['name']}\")
"
```

채널 ID를 찾으면 이후 API 호출에 사용한다.

---

## 자주 사용하는 API

### 메시지 보내기
```bash
curl -s -X POST https://slack.com/api/chat.postMessage \
  -H "Authorization: Bearer $SLACK_USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"channel": "채널ID", "text": "메시지 내용"}'
```

### 스레드에 답글 보내기
```bash
curl -s -X POST https://slack.com/api/chat.postMessage \
  -H "Authorization: Bearer $SLACK_USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"channel": "채널ID", "text": "답글", "thread_ts": "스레드타임스탬프"}'
```

### 메시지 수정
```bash
curl -s -X POST https://slack.com/api/chat.update \
  -H "Authorization: Bearer $SLACK_USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"channel": "채널ID", "ts": "메시지타임스탬프", "text": "수정된 내용"}'
```

### 메시지 삭제
```bash
curl -s -X POST https://slack.com/api/chat.delete \
  -H "Authorization: Bearer $SLACK_USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"channel": "채널ID", "ts": "메시지타임스탬프"}'
```

### 채널 히스토리 조회
```bash
curl -s "https://slack.com/api/conversations.history?channel=채널ID&limit=20" \
  -H "Authorization: Bearer $SLACK_USER_TOKEN"
```

### 스레드 조회
```bash
curl -s "https://slack.com/api/conversations.replies?channel=채널ID&ts=스레드타임스탬프" \
  -H "Authorization: Bearer $SLACK_USER_TOKEN"
```

### 메시지 검색
```bash
curl -s -G "https://slack.com/api/search.messages" \
  --data-urlencode "query=검색어" \
  -H "Authorization: Bearer $SLACK_USER_TOKEN"
```

### 리액션 추가
```bash
curl -s -X POST https://slack.com/api/reactions.add \
  -H "Authorization: Bearer $SLACK_USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"channel": "채널ID", "timestamp": "메시지타임스탬프", "name": "이모지명"}'
```

### 파일 업로드
```bash
curl -s -X POST https://slack.com/api/files.uploadV2 \
  -H "Authorization: Bearer $SLACK_USER_TOKEN" \
  -F "file=@파일경로" \
  -F "channel_id=채널ID" \
  -F "title=파일제목"
```

### 사용자 조회
```bash
curl -s "https://slack.com/api/users.list?limit=200" \
  -H "Authorization: Bearer $SLACK_USER_TOKEN"
```

### DM 열기
```bash
curl -s -X POST https://slack.com/api/conversations.open \
  -H "Authorization: Bearer $SLACK_USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"users": "사용자ID"}'
```

---

## API 문서 참조

모르는 메서드가 있거나 파라미터를 확인하고 싶을 때:

- **메서드 전체 목록**: https://api.slack.com/methods
- **개별 메서드 문서**: `https://api.slack.com/methods/{메서드명}`
  - 예: https://api.slack.com/methods/chat.postMessage
  - 예: https://api.slack.com/methods/conversations.history
  - 예: https://api.slack.com/methods/search.messages

URL 패턴이 일정하므로 메서드명만 알면 바로 문서를 찾을 수 있다.

---

## 응답 원칙

1. **메시지 전송/수정/삭제는 반드시 사용자에게 확인받는다** — 내용을 미리 보여주고 승인 후 실행
2. **조회 명령은 바로 실행한다** — 채널 목록, 히스토리, 검색 등은 확인 없이 실행
3. **결과를 읽기 좋게 정리한다** — JSON을 그대로 보여주지 않고 핵심 정보만 정리
4. **채널명을 자동으로 ID로 변환한다** — 사용자가 채널명을 입력하면 ID를 먼저 조회
5. **에러 발생 시 원인을 분석한다** — 권한 부족, 채널 미존재, 토큰 만료 등 안내

---

보고서는 한국어로 작성한다. 기술 용어나 고유명사는 원문 그대로 사용한다.

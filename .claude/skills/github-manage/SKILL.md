---
name: github-manage
description: GitHub CLI(gh)를 사용하여 PR 생성/조회/리뷰, 이슈 관리, 레포지토리 조회, 브랜치/릴리즈 관리, Actions 워크플로우 확인 등을 수행합니다. GH_TOKEN 환경변수 기반 인증으로 동작합니다. TRIGGER when: 사용자가 GitHub 관련 작업을 요청할 때. "github", "깃허브", "PR", "풀리퀘스트", "pull request", "이슈", "issue", "리뷰", "review", "머지", "merge", "브랜치", "branch", "릴리즈", "release", "actions", "워크플로우", "workflow", "체크", "checks", "레포", "repo" 등 관련 키워드가 포함될 때 사용. 단, git CLI 자체(commit, push, pull 등)는 이 스킬이 아닌 일반 Bash로 처리한다.
argument-hint: (자연어로 GitHub 관련 요청을 자유롭게 입력)
disable-model-invocation: false
context: compress
allowed-tools: Bash, Read, Grep, Glob, Edit
---

# GitHub 관리 (gh CLI + GH_TOKEN 인증)

## 환경 설정

`.env` 파일에서 아래 값을 읽어 사용한다.

```bash
source .env
```

- `GITHUB_TOKEN`: GitHub Personal Access Token (classic, `repo` scope 필요)

**모든 gh 명령 실행 시 `GH_TOKEN` 환경변수를 포함한다:**

```bash
GH_TOKEN=$GITHUB_TOKEN gh {command}
```

---

## 인증 확인

```bash
GH_TOKEN=$GITHUB_TOKEN gh auth status
```

인증이 유효하면 계정명, 토큰 scope 등이 표시된다.
토큰이 만료되었거나 유효하지 않으면 사용자에게 [GitHub 토큰 발급 페이지](https://github.com/settings/tokens)에서 새 토큰을 발급받아 `.env`의 `GITHUB_TOKEN` 값을 업데이트하도록 안내한다.

---

## 기본 조직

ADM 팀의 GitHub 조직은 `Buzzvil`이다. 사용자가 레포지토리를 지정할 때 조직명을 생략하면 `Buzzvil`을 기본값으로 사용한다.

---

## Pull Request

### PR 목록 조회

```bash
GH_TOKEN=$GITHUB_TOKEN gh pr list --repo Buzzvil/{repo} --state open --limit 20
```

**주요 플래그:**

| 플래그 | 설명 |
|--------|------|
| `--state` | `open`, `closed`, `merged`, `all` |
| `--author` | 작성자 필터 (예: `@me`, `Jin5823`) |
| `--label` | 라벨 필터 |
| `--base` | 베이스 브랜치 필터 |
| `--search` | 검색 쿼리 (GitHub 검색 문법) |
| `--limit` | 결과 수 제한 |
| `--json` | JSON 출력 (예: `--json number,title,state,author`) |

### PR 상세 조회

```bash
GH_TOKEN=$GITHUB_TOKEN gh pr view {number} --repo Buzzvil/{repo}
```

JSON으로 상세 정보:

```bash
GH_TOKEN=$GITHUB_TOKEN gh pr view {number} --repo Buzzvil/{repo} --json title,body,state,author,reviewRequests,reviews,labels,mergeStateStatus,checks
```

### PR 생성

```bash
GH_TOKEN=$GITHUB_TOKEN gh pr create --repo Buzzvil/{repo} \
  --base {base_branch} \
  --head {head_branch} \
  --title "{title}" \
  --body "$(cat <<'EOF'
## Summary
- 변경 사항 요약

## Test plan
- [ ] 테스트 항목
EOF
)"
```

### PR 리뷰 코멘트 조회

```bash
GH_TOKEN=$GITHUB_TOKEN gh api repos/Buzzvil/{repo}/pulls/{number}/comments --paginate | python3 -m json.tool
```

### PR 리뷰 요청

```bash
GH_TOKEN=$GITHUB_TOKEN gh pr edit {number} --repo Buzzvil/{repo} --add-reviewer {username}
```

### PR 머지

```bash
GH_TOKEN=$GITHUB_TOKEN gh pr merge {number} --repo Buzzvil/{repo} --squash --delete-branch
```

**머지 방식:**

| 플래그 | 설명 |
|--------|------|
| `--squash` | Squash merge |
| `--merge` | Merge commit |
| `--rebase` | Rebase merge |
| `--delete-branch` | 머지 후 브랜치 삭제 |

### PR 리뷰 스레드 조회 (resolve 상태 포함)

```bash
GH_TOKEN=$GITHUB_TOKEN gh api graphql -f query='
  query {
    repository(owner: "Buzzvil", name: "{repo}") {
      pullRequest(number: {number}) {
        reviewThreads(first: 100) {
          nodes {
            id
            isResolved
            comments(first: 3) {
              nodes { body author { login } }
            }
          }
        }
      }
    }
  }
'
```

### PR 리뷰 스레드 resolve

```bash
GH_TOKEN=$GITHUB_TOKEN gh api graphql -f query='
  mutation {
    resolveReviewThread(input: { threadId: "{thread_id}" }) {
      thread { id isResolved }
    }
  }
'
```

`thread_id`는 위 리뷰 스레드 조회에서 얻은 `id` 값 (예: `PRRT_kwDOARrwjs524iiA`).

### PR 리뷰 스레드 unresolve

```bash
GH_TOKEN=$GITHUB_TOKEN gh api graphql -f query='
  mutation {
    unresolveReviewThread(input: { threadId: "{thread_id}" }) {
      thread { id isResolved }
    }
  }
'
```

### PR diff 확인

```bash
GH_TOKEN=$GITHUB_TOKEN gh pr diff {number} --repo Buzzvil/{repo}
```

### PR 체크 상태

```bash
GH_TOKEN=$GITHUB_TOKEN gh pr checks {number} --repo Buzzvil/{repo}
```

---

## Issues

### 이슈 목록 조회

```bash
GH_TOKEN=$GITHUB_TOKEN gh issue list --repo Buzzvil/{repo} --state open --limit 20
```

### 이슈 상세 조회

```bash
GH_TOKEN=$GITHUB_TOKEN gh issue view {number} --repo Buzzvil/{repo}
```

### 이슈 생성

```bash
GH_TOKEN=$GITHUB_TOKEN gh issue create --repo Buzzvil/{repo} \
  --title "{title}" \
  --body "{body}" \
  --label "{label}" \
  --assignee "{username}"
```

### 이슈 코멘트 추가

```bash
GH_TOKEN=$GITHUB_TOKEN gh issue comment {number} --repo Buzzvil/{repo} --body "{comment}"
```

---

## Repository

### 레포지토리 조회

```bash
GH_TOKEN=$GITHUB_TOKEN gh repo view Buzzvil/{repo} --json name,description,defaultBranchRef,url
```

### 레포지토리 목록

```bash
GH_TOKEN=$GITHUB_TOKEN gh repo list Buzzvil --limit 30 --json name,description,updatedAt --jq '.[] | "\(.name)\t\(.description // "")\t\(.updatedAt[:10])"'
```

### 레포지토리 검색

```bash
GH_TOKEN=$GITHUB_TOKEN gh search repos --owner Buzzvil "{query}" --json name,description
```

---

## Actions (워크플로우)

### 워크플로우 실행 목록

```bash
GH_TOKEN=$GITHUB_TOKEN gh run list --repo Buzzvil/{repo} --limit 10
```

### 워크플로우 실행 상세

```bash
GH_TOKEN=$GITHUB_TOKEN gh run view {run_id} --repo Buzzvil/{repo}
```

### 워크플로우 실행 로그

```bash
GH_TOKEN=$GITHUB_TOKEN gh run view {run_id} --repo Buzzvil/{repo} --log
```

### 실패한 워크플로우만 조회

```bash
GH_TOKEN=$GITHUB_TOKEN gh run list --repo Buzzvil/{repo} --status failure --limit 10
```

---

## Release

### 릴리즈 목록

```bash
GH_TOKEN=$GITHUB_TOKEN gh release list --repo Buzzvil/{repo} --limit 10
```

### 릴리즈 상세

```bash
GH_TOKEN=$GITHUB_TOKEN gh release view {tag} --repo Buzzvil/{repo}
```

---

## API 직접 호출

`gh api`를 사용하면 GitHub REST/GraphQL API를 직접 호출할 수 있다. 위 명령으로 해결되지 않는 작업에 활용한다.

### REST API

```bash
GH_TOKEN=$GITHUB_TOKEN gh api repos/Buzzvil/{repo}/branches --paginate | python3 -m json.tool
```

### GraphQL API

```bash
GH_TOKEN=$GITHUB_TOKEN gh api graphql -f query='
  query {
    repository(owner: "Buzzvil", name: "{repo}") {
      pullRequests(first: 10, states: OPEN) {
        nodes {
          number
          title
          author { login }
        }
      }
    }
  }
'
```

---

## gh CLI 자체 도움말

명령이나 플래그가 확실하지 않을 때는 `--help`로 확인한다:

```bash
gh pr --help
gh pr create --help
gh api --help
```

---

## GraphQL API 가이드

`gh api graphql`을 사용하면 REST API로 불가능하거나 비효율적인 작업을 수행할 수 있다. 리뷰 스레드 resolve, 복잡한 필터링, 여러 리소스 동시 조회 등이 대표적이다.

### 기본 문법

```bash
GH_TOKEN=$GITHUB_TOKEN gh api graphql -f query='
  query {
    repository(owner: "Buzzvil", name: "{repo}") {
      # 여기에 쿼리 작성
    }
  }
'
```

### 변수 사용 (파라미터 바인딩)

쿼리에 변수를 사용하면 가독성과 재사용성이 높아진다:

```bash
GH_TOKEN=$GITHUB_TOKEN gh api graphql \
  -F owner='Buzzvil' \
  -F repo='{repo}' \
  -F number:='123' \
  -f query='
    query($owner: String!, $repo: String!, $number: Int!) {
      repository(owner: $owner, name: $repo) {
        pullRequest(number: $number) {
          title
          state
        }
      }
    }
  '
```

- `-f key=value`: 문자열 변수
- `-F key:=123`: 숫자/불리언 변수 (`:=` 사용)

### Mutation (쓰기 작업)

```bash
GH_TOKEN=$GITHUB_TOKEN gh api graphql -f query='
  mutation {
    addComment(input: { subjectId: "{node_id}", body: "코멘트 내용" }) {
      commentEdge { node { id } }
    }
  }
'
```

### 페이지네이션

대량 데이터 조회 시 커서 기반 페이지네이션을 사용한다:

```bash
GH_TOKEN=$GITHUB_TOKEN gh api graphql -f query='
  query {
    repository(owner: "Buzzvil", name: "{repo}") {
      pullRequests(first: 10, after: "{end_cursor}", states: OPEN) {
        pageInfo {
          hasNextPage
          endCursor
        }
        nodes {
          number
          title
        }
      }
    }
  }
'
```

### 자주 쓰는 GraphQL 작업

| 작업 | Mutation/Query |
|------|----------------|
| 리뷰 스레드 resolve | `resolveReviewThread(input: { threadId })` |
| 리뷰 스레드 unresolve | `unresolveReviewThread(input: { threadId })` |
| PR 코멘트 추가 | `addComment(input: { subjectId, body })` |
| 라벨 추가 | `addLabelsToLabelable(input: { labelableId, labelIds })` |
| PR approve | `addPullRequestReview(input: { pullRequestId, event: APPROVE })` |
| PR request changes | `addPullRequestReview(input: { pullRequestId, event: REQUEST_CHANGES, body })` |

### 스키마 탐색

GraphQL 스키마에서 사용 가능한 필드나 타입을 모를 때:

```bash
# 특정 타입의 필드 목록 조회
GH_TOKEN=$GITHUB_TOKEN gh api graphql -f query='
  query {
    __type(name: "PullRequest") {
      fields { name description }
    }
  }
'
```

공식 스키마 문서: https://docs.github.com/en/graphql/reference

---

## 응답 원칙

1. **인증 확인을 먼저 한다** — 모든 작업 전 `gh auth status`로 토큰 유효성을 확인한다. 실패 시 토큰 갱신을 안내한다.
2. **조직명은 기본 `Buzzvil`** — 사용자가 레포만 말하면 `Buzzvil/{repo}`로 자동 보완한다.
3. **PR 머지, 이슈 close 등 쓰기 작업은 사용자에게 확인받는다** — 대상과 내용을 보여주고 승인 후 실행한다.
4. **조회 명령은 바로 실행한다** — PR 목록, 이슈 조회, 체크 상태 등은 확인 없이 즉시 실행한다.
5. **결과를 읽기 좋게 정리한다** — JSON을 그대로 보여주지 않고 핵심 정보만 표 또는 목록으로 정리한다.
6. **에러 발생 시 원인을 분석한다** — 인증 만료, 권한 부족, 리소스 미존재 등 원인을 파악하여 안내한다.
7. **PR body 작성 시 줄바꿈을 올바르게 처리한다** — `\n` 리터럴이 아닌 실제 줄바꿈(heredoc 사용)으로 작성한다.

---

보고서는 한국어로 작성한다. 기술 용어나 고유명사는 원문 그대로 사용한다.

---
name: aws-manage
description: AWS 리소스를 aws-vault + AWS CLI로 조회하고 관리합니다. MCP 대신 CLI 기반으로 동작합니다. TRIGGER when: 사용자가 AWS 관련 질문을 하거나 AWS 리소스(S3, EC2, EKS, IAM, Lambda, CloudWatch, RDS, DynamoDB 등)를 조회/관리하려 할 때. "aws", "s3", "ec2", "eks", "lambda", "iam", "cloudwatch", "rds", "dynamodb", "버킷", "인스턴스", "클러스터", "배포", "로그" 등 AWS 서비스나 인프라 관련 키워드가 포함될 때 사용.
argument-hint: (자연어로 AWS 관련 요청을 자유롭게 입력)
disable-model-invocation: false
context: compress
allowed-tools: Bash, Read, Grep, Glob
---

# AWS 리소스 관리 (aws-vault + AWS CLI)

## 환경 설정

### 프로필 확인 및 선택

`aws-vault list`를 실행하여 사용 가능한 프로필 목록을 확인한다.
프로필명과 요청 맥락을 기반으로 적절한 프로필을 자동 선택한다:

- EKS, Kubernetes 관련 → `eks` 가 포함된 프로필 우선
- 그 외 일반 AWS 리소스 → `backend` 가 포함된 프로필 우선
- `-ro` 접미사가 붙은 프로필은 읽기 전용이므로, 변경 작업에는 사용하지 않는다
- 맥락으로 판단이 어려우면 사용자에게 어떤 프로필을 쓸지 물어본다

---

## 명령 실행 방식

모든 AWS CLI 명령은 반드시 `aws-vault exec`를 통해 실행한다:

```bash
aws-vault exec {프로필명} -- aws {서비스} {명령} [옵션]
```

### SSO 세션 만료 시

명령 실행 중 인증 오류가 발생하면:
1. 사용자에게 SSO 세션이 만료되었음을 알린다
2. `aws-vault login {프로필명}`을 바로 실행한다
3. 사용자가 브라우저에서 인증을 완료할 때까지 기다린다
4. 인증 완료 후 원래 요청했던 명령을 다시 실행한다

### 모르는 명령이 있을 때

특정 서비스나 명령의 사용법을 모르면 `--help`를 활용한다:

```bash
aws-vault exec {프로필명} -- aws {서비스} help
aws-vault exec {프로필명} -- aws {서비스} {명령} help
```

---

## 응답 원칙

1. **결과를 읽기 좋게 정리한다** — JSON 출력을 그대로 보여주지 않고, 핵심 정보를 표 또는 목록으로 정리한다
2. **위험한 명령은 반드시 확인한다** — 리소스 삭제, 수정, 생성 등 변경 작업은 실행 전 사용자에게 확인을 받는다
3. **읽기 전용 명령은 바로 실행한다** — `list`, `describe`, `get` 등 조회 명령은 확인 없이 바로 실행한다
4. **최소 권한 원칙** — 요청에 필요한 최소한의 명령만 실행한다
5. **에러 발생 시 원인을 분석한다** — 권한 부족, 리전 오류, 리소스 미존재 등 원인을 파악하여 안내한다

---

## 자주 사용하는 명령 참고

### S3
```bash
aws s3 ls                              # 버킷 목록
aws s3 ls s3://{버킷명}/               # 버킷 내 객체 목록
aws s3 cp {로컬경로} s3://{버킷명}/    # 파일 업로드
```

### EC2
```bash
aws ec2 describe-instances             # 인스턴스 목록
aws ec2 describe-security-groups       # 보안 그룹
```

### EKS
```bash
aws eks list-clusters                  # 클러스터 목록
aws eks describe-cluster --name {name} # 클러스터 상세
```

### IAM
```bash
aws iam list-users                     # 사용자 목록
aws iam list-roles                     # 역할 목록
```

### CloudWatch
```bash
aws cloudwatch list-metrics            # 메트릭 목록
aws logs describe-log-groups           # 로그 그룹 목록
```

### Lambda
```bash
aws lambda list-functions              # 함수 목록
```

### Cost Explorer
```bash
aws ce get-cost-and-usage --time-period Start={시작},End={종료} --granularity MONTHLY --metrics BlendedCost
```

위 목록은 참고용이며, 사용자의 요청에 따라 어떤 AWS 서비스 명령이든 실행할 수 있다.
`aws help`를 통해 사용 가능한 전체 서비스 목록을 확인할 수 있다.

---

보고서는 한국어로 작성한다. 기술 용어나 고유명사는 원문 그대로 사용한다.

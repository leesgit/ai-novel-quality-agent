# Hosting (R5)

해커톤 요건 R5("URL to the hosted Project") 충족 경로. 두 단계.

## 1단계 — 로컬 호스팅 (무료, 기본)

`adk web`이 QualityAnalyst를 FastAPI + Web UI로 띄운다. 심사자가 브라우저에서
에이전트와 직접 대화하며 진단을 받아볼 수 있다.

```bash
./scripts/serve_demo.sh        # Phoenix + mock 적재 + adk web (localhost:8000)
```

구성:
- Phoenix observability → `http://localhost:6006`
- QualityAnalyst Web UI → `http://localhost:8000` (`/list-apps` → `["quality_analyst"]`)

심사자는 `git clone` → venv 셋업 → `.env`에 무료 Gemini key → 위 한 명령으로 **재현**한다.
데모 영상이 이 흐름을 보여준다.

## 2단계 — Cloud Run public URL (선택, 소액 크레딧)

진짜 공개 URL이 필요하면:

```bash
# QualityAnalyst를 Cloud Run에 배포
.venv-adk/bin/adk deploy cloud_run \
  --project <GCP_PROJECT> --region us-central1 \
  agents_dir/quality_analyst
# → https://quality-analyst-xxxx.run.app
```

이때 Phoenix는 로컬이 아니라 **Phoenix Cloud 무료 인스턴스**를 써야 한다:
- https://phoenix.arize.com 가입 → API key 발급
- `.env`: `PHOENIX_BASE_URL=https://app.phoenix.arize.com`, `PHOENIX_API_KEY=...`

비용:
- Cloud Run: 요청당 과금이나 무료 등급이 큼 → 데모 트래픽은 거의 0원
- Gemini: 무료 AI Studio key → 0원
- Phoenix Cloud: 무료 티어

> ⚠️ Cloud Run 배포는 GCP 크레딧을 소량 쓸 수 있으므로 배포 전 확인할 것.

## 환경변수 요약

| 변수 | 용도 | 기본 |
|---|---|---|
| `GOOGLE_API_KEY` | Gemini (필수) | — |
| `PHOENIX_BASE_URL` | Phoenix 엔드포인트 | `http://localhost:6006` |
| `PHOENIX_API_KEY` | Phoenix Cloud용 | (로컬은 불필요) |
| `GCP_PROJECT_ID` | 설정 시 Vertex 모드(과금) | (미설정 = 무료 GenAI) |

> `GCP_PROJECT_ID`를 비워두면 ADK가 무료 GenAI(API key) 모드로 동작한다. Vertex(과금) 회피.

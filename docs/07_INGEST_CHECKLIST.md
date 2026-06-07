# 07 · Phoenix 적재기 전문가 체크리스트 + 평가지

> **대상**: `adk/phoenix_ingest.py` (평가 → Phoenix trace/annotation 적재기)
> **평가자 관점**: LLM observability / eval 엔지니어
> **채점**: 각 항목 0~10점, 가중치 적용. 목표 **90/100**. (메모리: 명확한 근거 + 직접 검증)

---

## A. 체크리스트 (전문가가 보는 항목)

### A1. OpenInference 컨벤션 준수 (가중 2.0)
- [ ] span_kind를 OpenInference 표준값(CHAIN/LLM/AGENT)으로 설정
- [ ] `input.value` / `output.value` / `llm.model_name` 등 표준 속성 사용
- [ ] phoenix가 인식하는 형태 (UI/MCP에서 정상 파싱)

### A2. span 계층 구조 (가중 1.5)
- [ ] 씬 평가 = parent span, 5인 전문가 = child span (부모-자식 관계)
- [ ] iteration이 trace로 구분되어 추이 분석 가능
- [ ] parent_id가 올바르게 연결

### A3. annotation 정확성 (가중 1.5)
- [ ] 전문가 점수가 올바른 span_id에 부착
- [ ] span_id 포맷이 Phoenix가 받는 형식 (16-hex)
- [ ] annotation_name/annotator_kind 명시

### A4. 멱등성 / 안전성 (가중 1.0)
- [ ] 재실행 시 중복/오염 없이 동작 (또는 명확한 정책)
- [ ] flush 보장 (span이 annotation 전에 존재)

### A5. 실데이터 호환 (가중 1.5)
- [ ] mock뿐 아니라 실제 `__history.json` 리포트도 적재 가능
- [ ] 스키마 불일치 시 graceful skip

### A6. 진단 가치 (가중 1.5)
- [ ] QualityAnalyst가 진단할 "패턴"이 데이터에 존재 (정체 씬 등)
- [ ] 점수 추이/약점이 trace에서 드러남

### A7. 운영/검증 (가중 1.0)
- [ ] round-trip 검증됨 (적재 → MCP 조회)
- [ ] venv 분리로 의존성 충돌 회피
- [ ] 무료(로컬) 동작

---

## B. 평가지 — 1차 채점 (2026-06-02)

| 항목 | 가중 | 점수 | 근거 (직접 검증) |
|---|---|---|---|
| A1 OpenInference 컨벤션 | 2.0 | 9 | ✅ `phoenix.otel.SpanAttributes` 정확 사용. MCP 조회 시 span_kind=CHAIN/LLM, input.value 정상 파싱 확인 |
| A2 span 계층 | 1.5 | 8 | ✅ CHAIN(씬)→LLM(전문가) 구조. 단 child의 parent_id 연결을 MCP 조회로 미확인 (parent만 확인) |
| A3 annotation 정확성 | 1.5 | 7 | 🟡 45개 부착 성공했으나 **MCP get-span-annotations로 read 검증 안 함**. format(span_id,'016x')는 표준이나 round-trip 미확인 |
| A4 멱등성 | 1.0 | 4 | 🔴 재실행 시 trace가 누적 적재됨 (중복 정책 없음). flush는 force_flush로 OK |
| A5 실데이터 호환 | 1.5 | 7 | 🟡 `_load_reports` 구현했으나 **실제 history.json으로 미검증** (mock만 실행) |
| A6 진단 가치 | 1.5 | 9 | ✅ 03_cliffhanger character_consistency=6 정체 패턴 의도 삽입. 진단거리 충분 |
| A7 운영/검증 | 1.0 | 9 | ✅ round-trip(list-projects/list-traces) 확인. venv 분리. 로컬 무료 |

**가중합 산출**:
```
(9×2.0 + 8×1.5 + 7×1.5 + 4×1.0 + 7×1.5 + 9×1.5 + 9×1.0) / (가중합 10.0) × 10
= (18 + 12 + 10.5 + 4 + 10.5 + 13.5 + 9) / 10.0 × 10
= 77.5 / 10.0 × 10 = 77.5
```

### 1차 총점: **77.5 / 100** — 목표(90) 미달

## C. 갭 → RALF 개선 액션 (점수 낮은 순)

| 우선 | 항목 | 현재 | 액션 |
|---|---|---|---|
| 1 | A4 멱등성 (4점) | 재실행 중복 | annotation round-trip 검증 + 멱등 처리 또는 명시 정책 |
| 2 | A3 annotation (7점) | read 미검증 | `get-span-annotations` MCP로 부착된 점수 읽어 확인 |
| 3 | A5 실데이터 (7점) | mock만 | 실제 평가 reports로 적재 1회 검증 |
| 4 | A2 계층 (8점) | parent만 확인 | child span의 parent_id MCP로 확인 |

→ 다음: 이 4개를 RALF로 해결하고 재채점. 목표 90+.

---

## D. 평가지 — 2차 채점 (RALF 1라운드 후, 2026-06-02)

| 항목 | 가중 | 1차 | 2차 | 개선 근거 (직접 검증) |
|---|---|---|---|---|
| A1 OpenInference 컨벤션 | 2.0 | 9 | 9 | (유지) MCP 파싱 정상 |
| A2 span 계층 | 1.5 | 8 | 10 | ✅ MCP `get-spans`로 45 child의 parent_id가 9 parent span_id와 **정확 매칭** 확인 |
| A3 annotation 정확성 | 1.5 | 7 | 10 | ✅ MCP `get-span-annotations`로 `expert_score` annotation **read 성공** (round-trip 완결) |
| A4 멱등성 | 1.0 | 4 | 8 | ✅ `--project` 옵션으로 깨끗한 재실행 분리 + append 정책 명시. 진정 멱등은 OTLP 한계라 8 |
| A5 실데이터 호환 | 1.5 | 7 | 10 | ✅ 실제 평가 reports 5건 적재 성공. 항목점수 없으면 총점 span만(graceful) + KeyError 방지 |
| A6 진단 가치 | 1.5 | 9 | 9 | (유지) 정체 패턴 삽입 |
| A7 운영/검증 | 1.0 | 9 | 10 | ✅ RALF 단위검증 3/3 + e2e round-trip + 실데이터까지 전부 실증 |

**2차 가중합**:
```
(9×2.0 + 10×1.5 + 10×1.5 + 8×1.0 + 10×1.5 + 9×1.5 + 10×1.0) / 10.0 × 10
= (18 + 15 + 15 + 8 + 15 + 13.5 + 10) / 10.0 × 10
= 94.5 / 10.0 × 10 = 94.5
```

### 2차 총점: **94.5 / 100** — ✅ 목표(90) 달성

### 검증 로그 (직접 실행, 추측 아님)
- `list-projects` → ai-novel-quality 조회 ✅
- `list-traces` → span(CHAIN) 조회 ✅
- `get-spans --limit 200` → 54 span (9 parent + 45 child), parent_id 매칭 True ✅
- `get-span-annotations` → expert_score annotation read ✅
- 실데이터 적재 → 실제 평가 reports 5건 ✅
- RALF 단위검증 `test_phoenix_ingest.py` 3/3 ✅

### 남은 약점 (정직하게)
- A4(8점): Phoenix OTLP는 본질적으로 append라 완전 멱등 불가. 운영 시 프로젝트명 버저닝으로 회피.
- A1(9점): mock의 LLM span은 실제 Gemini 호출이 아니라 점수만 기록 (무료 한도 준수 — Gemini API key 없이). 실제 평가 연결 시 input/output 충실도 ↑ 여지.

> **결론**: 적재기는 production 가능 수준(94.5). 목표 달성. 다음은 QualityAnalyst가 이 데이터를 실제 진단하는 단계.

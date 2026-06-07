"""ADK 멀티에이전트 레이어.

기존 scripts/ 파이프라인을 Google ADK 멀티에이전트로 감싸는 add-on 레이어다.
scripts/ 코드는 수정하지 않는다 — 여기서 subprocess/import로 호출만 한다.

별도 venv(.venv-adk, Python 3.11)에서 실행:
    .venv-adk/bin/python -m adk.main --storyboard projects/<name>/storyboard.json --scene <id>
"""

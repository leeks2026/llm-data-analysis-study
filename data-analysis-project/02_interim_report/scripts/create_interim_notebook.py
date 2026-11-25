"""Create the second-stage-only notebook. It never invokes the final-stage pipeline."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def markdown(text):
    return {"cell_type": "markdown", "metadata": {}, "source": text.splitlines(keepends=True)}


def code(text):
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
            "source": text.splitlines(keepends=True)}


cells = [
    markdown("""# 2차 중간 분석: 서울 지하철 이용과 강수 기록

서울교통공사 관할 구간의 2023~2025년 승하차와 서울 ASOS(108) 일자료를 날짜 기준으로 결합한다. 이 Notebook은 자료 검증과 기초 탐색 분석만 수행한다. 강수량 빈칸은 0으로 채우지 않는다.
"""),
    code("""from pathlib import Path
import os, sys, subprocess, json
import pandas as pd
from IPython.display import display, Image
ROOT = Path.cwd()
if not (ROOT / 'scripts').exists():
    ROOT = ROOT.parent
os.chdir(ROOT)
print('Project:', ROOT)
print('Python:', sys.version.split()[0])
"""),
    markdown("""## 1. 2차 전용 자료 검증과 기초 분석 실행

원자료 적재, 후보 고유키와 공통 역 범위 확인, 시간대 변환과 날짜 결합 검증, 기초 표·그림을 실행한다.
"""),
    code("""run = subprocess.run([sys.executable, 'scripts/run_interim.py'], text=True,
                     encoding='utf-8', errors='replace', capture_output=True)
print(run.stdout)
if run.stderr:
    print(run.stderr)
assert run.returncode == 0, f'2차 실행 실패: {run.returncode}'
"""),
    markdown("""## 2. 출처·고유키·원본 직접 대조

고유키는 날짜·호선·역번호·승하차구분이다. 원자료의 서울역 1호선 특정 행을 정규화된 값과 직접 비교한다.
"""),
    code("""base = Path('results/interim/tables')
display(pd.read_csv(base / 'subway_source_audit.csv'))
display(pd.read_csv(base / 'source_direct_comparison.csv'))
display(pd.read_csv(base / 'reshape_validation.csv'))
"""),
    markdown("""## 3. 강수 표기와 날짜 결합

0.0mm 기록과 빈칸은 별도다. 빈칸 중 보조항목으로 구분한 후보는 미확인 상태다.
"""),
    code("""with open('results/interim/weather_merge_audit.json', encoding='utf-8') as f:
    weather_audit = json.load(f)
print(json.dumps(weather_audit, ensure_ascii=False, indent=2))
display(pd.read_csv(base / 'rain_vs_duration_crosscheck.csv'))
"""),
    markdown("""## 4. 요일·강수 기록별 기초 결과

공통 역의 날짜별 06~24시 승차 건수를 요일과 강수 기록으로 나눠 살펴본다. 빈칸 후보는 확정된 무강수가 아니다.
"""),
    code("""display(pd.read_csv(base / 'weekday_boardings.csv'))
display(pd.read_csv(base / 'precip_weekend_descriptive.csv'))
display(pd.read_csv(base / 'rain_intensity_by_weekend.csv'))
"""),
    code("""display(Image(filename='results/interim/figures/01_weekday_boardings.png'))
display(Image(filename='results/interim/figures/02_precipitation_records.png'))
"""),
    code("""display(Image(filename='results/interim/figures/03_hourly_by_daily_precipitation.png'))
"""),
    markdown("""## 5. 중간 해석과 한계

- 일강수량은 특정 시간대에 비가 왔다는 뜻이 아니다. 눈 등도 강수량에 포함된다.
- 기상관측소 한 지점이 모든 역 주변의 날씨를 대표하지 못할 수 있다.
- 빈칸 후보는 무강수 확정값이 아니며, 공휴일·행사·운행 변화가 단순 비교에 영향을 줄 수 있다.
- 원자료 출처, AI 활용과 검증 기록은 별첨 자료를 참고한다.
"""),
]
notebook = {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
               "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}
for i, cell in enumerate(cells):
    cell["id"] = f"interim-{i:02d}"
path = ROOT / "notebooks" / "02_중간분석.ipynb"
path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("Created", path)

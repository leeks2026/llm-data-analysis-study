# 2차 중간보고: 비가 오는 날, 서울 지하철 이용은 어떻게 달라지는가?

2023~2025년 서울교통공사 지하철과 기상청 서울 관측자료를 결합한 중간 단계 자료입니다. 기존 자료 확보·결합 점검은 **2026년 11월 24일 14:40 기준**이며, 같은 입력을 이용한 계절·시간대·분포 기초 탐색은 **2026년 11월 26일** Codespaces에서 추가로 실행했습니다. 별첨에는 각 화면의 수행 시점을 구분해 표시했습니다.

## 보고서와 실행 자료

- [중간보고서 PDF — 본문 및 별첨](reports/02_중간보고서_별첨포함_확장.pdf)
- [기존 중간 분석 Notebook](notebooks/02_중간분석.ipynb)
- 기존 Notebook에는 앞선 중간 분석의 실행 결과가 포함되어 있습니다. 추가 탐색의 실제 실행 기록과 결과는 아래 로그·표·화면에서 확인할 수 있습니다.
- [추가 분석 결과표·실행 및 검증 로그](results/interim/enriched_eda/)
- [Codespaces 실행 화면](results/interim/captures/)
- [자료 처리 및 확인 코드](scripts/) · [검증 코드](tests/) · [원자료](data/raw/)

## 자료와 해석 범위

- [서울 열린데이터광장: 서울교통공사 역별 일별 시간대별 승하차인원](https://data.seoul.go.kr/dataList/OA-12921/F/1/datasetView.do)
- [기상청 기상자료개방포털: 종관기상관측(ASOS)](https://data.kma.go.kr/data/grnd/selectAsosRltmList.do?pgmNo=36)
- 대상은 2023~2025년 승차와 하차 기록이 공통으로 확인되는 272개 역·호선 코드의 06~24시 승차 건수입니다. 승차 건수는 고유 이용자 수가 아닙니다.
- 추가 분석은 **하루 전체 일강수 기록**을 기준으로 구분한 기술통계입니다. 해당 시간에 실제로 비가 왔다는 뜻이 아닙니다. 0.0mm 기록과 빈칸은 구분하고, 무강수 후보는 확정 무강수로 취급하지 않습니다.
- 평일은 월~금이며 공휴일이 포함됩니다. 2차의 일별 집단 비교와 이후 공휴일을 제외하고 같은 시간의 기상자료를 맞추는 분석은 대상과 기준이 다릅니다.
- 관찰된 차이를 강수의 인과 효과나 다른 교통수단으로의 전환으로 해석할 수 없습니다.

## 재현 방법

이 폴더를 작업 디렉터리로 사용해 Python 환경을 준비한 뒤 실행합니다.

~~~bash
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: ./.venv/Scripts/Activate.ps1
python -m pip install -r requirements.txt
python scripts/run_interim.py
python scripts/build_hourly_subway_input.py
python scripts/show_interim_hourly_quality.py
python scripts/run_interim_enrichment.py
python -m unittest discover -s tests -p test_interim_integrity.py -v
python -m unittest discover -s tests -p test_interim_enrichment.py -v
~~~

추가 분석은 `results/interim/tables/daily_joined.csv`와 `results/tables/hourly_subway.csv`를 입력으로 사용합니다. 기존 일별 입력과 시간대별 승차 합계를 날짜별로 대조하고 결과를 `results/interim/enriched_eda/`에 저장합니다. 운영체제에 따라 CSV의 줄바꿈이 달라 파일 해시가 다를 수 있으므로, 기록된 입력 해시와 날짜·시간·승차 건수의 내용 대조를 함께 확인합니다.

보고서를 다시 만들 때는 `python scripts/build_interim_enriched_report.py`를 실행합니다. Windows에서는 맑은 고딕 글꼴을 사용합니다. 다른 환경에서는 한글 TrueType 글꼴의 일반·굵은 파일을 각각 `INTERIM_FONT_REGULAR`와 `INTERIM_FONT_BOLD` 환경 변수로 지정해야 합니다. 원자료의 출처와 해시는 `data/raw/subway/provenance.json`에 있습니다.

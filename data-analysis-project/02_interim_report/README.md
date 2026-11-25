# 2차 중간보고: 비가 오는 날, 서울 지하철 이용은 어떻게 달라지는가?

2023~2025년 서울교통공사 지하철과 기상청 서울 관측자료를 결합해 강수와 지하철 이용의 관계를 살펴보는 프로젝트의 중간 단계 자료입니다. 2차 현황은 **2026년 11월 24일 14:40 기준**으로 정리했습니다.

## 보고서와 주요 자료

- [중간보고서 PDF — 본문 및 별첨](reports/02_중간보고서_별첨포함_확장.pdf)
- [실행 결과가 포함된 중간 분석 Notebook](notebooks/02_중간분석.ipynb)
- [기초 분석 결과표와 그림](results/interim/)
- [Codespaces 실행 화면](results/interim/captures/)
- [자료 처리 및 확인 코드](scripts/) · [검증 코드](tests/) · [원자료](data/raw/)

보고서의 일부 별첨 화면은 기준 시점에 확보한 같은 입력을 이후 다시 확인한 기록입니다. 보고서에 기재된 비공개 저장소 안내는 보고서 작성 당시 원본 저장소의 상태이며, 이 폴더는 해당 중간 단계 자료를 공개한 사본입니다.

## 자료와 해석 범위

- [서울 열린데이터광장: 서울교통공사 역별 일별 시간대별 승하차인원](https://data.seoul.go.kr/dataList/OA-12921/F/1/datasetView.do)
- [기상청 기상자료개방포털: 종관기상관측(ASOS)](https://data.kma.go.kr/data/grnd/selectAsosRltmList.do?pgmNo=36)
- 대상은 2023~2025년 승차와 하차 기록이 공통으로 확인되는 272개 역·호선 코드의 06~24시 승차 건수입니다. 지하철 승차 건수는 고유 이용자 수가 아닙니다.
- 일강수량으로 분류한 날의 시간대별 이용 패턴은 해당 시간에 비가 왔다는 뜻이 아닙니다. 강수량 빈칸과 0.0mm 기록은 구분하며, 무강수 후보는 확인되지 않은 후보로 취급합니다.
- 2차에는 자료 확인과 기초 탐색 결과를 담았습니다. 관찰된 차이를 강수의 인과 효과나 다른 교통수단으로의 전환으로 해석할 수 없습니다.

## 재현 방법

이 폴더를 작업 디렉터리로 사용하고 Python 환경을 준비한 뒤 다음 순서로 실행합니다.

~~~bash
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: ./.venv/Scripts/Activate.ps1
python -m pip install -r requirements.txt
python scripts/run_interim.py
python scripts/build_hourly_subway_input.py
python scripts/show_interim_hourly_quality.py
python -m unittest discover -s tests -p test_interim_integrity.py -v
~~~

results/interim/은 일별 결합과 기초 분석 결과이며, results/tables/hourly_subway.csv는 시간별 지하철 집계입니다. 원자료의 출처와 해시는 data/raw/subway/provenance.json에서 확인할 수 있습니다.

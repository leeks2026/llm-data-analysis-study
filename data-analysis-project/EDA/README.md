# 서울 지하철 승차와 강수량: 탐색적 자료 분석

이 폴더는 서울 지하철 승차 자료와 기상청 서울 관측소의 **일강수 기록**을 이용해 수행한 2차 중간 단계의 탐색적 자료 분석(EDA)을 정리한 공간입니다. 2023년부터 2025년까지의 자료를 사용했으며, 본문의 수치와 해석 범위는 [2차 중간보고서](../02_interim_report/reports/02_중간보고서_별첨포함_확장.pdf)와 일치합니다.

## 먼저 볼 문서

- [EDA 요약](EDA_요약.md): 분석 목적, 자료 범위, 주요 결과와 해석상의 한계
- [EDA 상세 과정 및 결과](EDA_상세_과정_및_결과.md): 자료 수집·정제, 집단 정의, 결과표, 검증과 재현 방법

## 자료와 실행 결과

| 항목 | 위치 |
| --- | --- |
| 추가 분석 코드 | [run_interim_enrichment.py](../02_interim_report/scripts/run_interim_enrichment.py) |
| 기본 자료 처리 및 탐색 코드 | [run_interim.py](../02_interim_report/scripts/run_interim.py) |
| 기존 실행 결과가 포함된 노트북 | [02_중간분석.ipynb](../02_interim_report/notebooks/02_중간분석.ipynb) |
| 추가 탐색 결과표와 실행·검증 기록 | [enriched_eda](../02_interim_report/results/interim/enriched_eda/) |
| 원자료와 기초 결과표 | [원자료](../02_interim_report/data/raw/), [기초 결과표](../02_interim_report/results/interim/tables/) |
| 실제 Codespaces 실행 화면 | [캡처 폴더](../02_interim_report/results/interim/captures/) |
| EDA 그림 생성 코드 | [create_eda_figures.py](create_eda_figures.py) |
| EDA 그림 생성 실행 기록 | [figures_execution.txt](figures_execution.txt) |

결과표와 원자료의 기준 파일은 `02_interim_report`에 두고 이 폴더에서 연결했습니다. 그림은 기존 결과표를 읽어 만든 표현 자료입니다. 기본 노트북의 실행 결과와 추가 탐색의 코드·로그는 별도로 기록되어 있습니다.

**해석 범위:** 분석에서 쓰는 강수량은 하루 전체 기록입니다. 미확인 무강수 후보는 확정 무강수일이 아니고 평일에는 공휴일이 포함됩니다. 기술통계의 차이는 강수의 인과 효과나 다른 교통수단으로의 전환을 입증하지 않습니다. 같은 시간의 기상자료를 결합하는 분석은 이후 단계에서 다룰 계획입니다.

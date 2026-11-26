"""Build the revised stage-two report from the archived interim evidence only."""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Drawing, Line, PolyLine, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Flowable, Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Table, TableStyle


HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
INTERIM = PROJECT / "results" / "interim"
TABLES = INTERIM / "tables"
CAPTURES = INTERIM / "captures"
ENRICHED = INTERIM / "enriched_eda"
OUTPUT = PROJECT / "reports"
OUTPUT.mkdir(parents=True, exist_ok=True)
REPORT = OUTPUT / "02_중간보고서_별첨포함_확장.pdf"


def read_csv(name: str) -> list[dict[str, str]]:
    with (TABLES / name).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


year_audit = read_csv("subway_source_audit.csv")
reshape_audit = read_csv("reshape_validation.csv")
daily_groups = read_csv("precip_weekend_descriptive.csv")
daily_intensity = read_csv("rain_intensity_by_weekend.csv")
profiles = read_csv("hourly_profile.csv")
weather = json.loads((INTERIM / "weather_merge_audit.json").read_text(encoding="utf-8"))
hourly = json.loads((INTERIM / "hourly_input_audit_1440.json").read_text(encoding="utf-8"))
enriched_audit = json.loads((ENRICHED / "analysis_audit.json").read_text(encoding="utf-8"))


def read_enriched(name: str) -> list[dict[str, str]]:
    with (ENRICHED / name).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


seasonal = read_enriched("seasonal_daily_comparison.csv")
periods = read_enriched("weekday_period_by_daily_rain.csv")
distributions = read_enriched("daily_distribution.csv")

# Refuse to build a report if the archival inputs do not match the stated snapshot.
assert [int(x["valid_rows"]) for x in year_audit] == [199270, 199410, 199290]
assert [int(x["fully_empty_rows"]) for x in year_audit] == [0, 0, 134]
assert all(int(x["candidate_key_duplicate_rows"]) == 0 for x in year_audit)
assert all(x["equal"] == "True" for x in reshape_audit)
assert weather["rows"] == 1096 and weather["unmatched_subway_dates"] == 0
assert weather["hourly_rows_before_merge"] == weather["hourly_rows_after_merge"] == 87680
assert weather["rain_category_counts"] == {
    "blank_unresolved": 628, "at_least_0.1mm": 336, "recorded_0.0mm": 132
}
assert weather["dry_candidates_unconfirmed"] == 625
assert hourly["observations"] == 26304
assert hourly["precipitation_values"] == {"blank": 23110, "zero": 1377, "positive": 1817}
assert hourly["daily_sum_diagnostic"]["same_date"]["close_within_0_05_mm"] == 187
assert hourly["daily_sum_diagnostic"]["shift_back_one_hour"]["close_within_0_05_mm"] == 336
assert enriched_audit["daily_dates"] == 1096 and enriched_audit["hourly_common_boarding_rows"] == 19728
assert enriched_audit["period_date_rows"] == 3288 and enriched_audit["hourly_sums_equal_daily"]
assert enriched_audit["group_counts"] == {"candidate_unconfirmed": 625, "rain_at_least_0.1": 336,
                                           "recorded_0.0": 132, "other_or_unresolved": 3}

regular = Path(os.environ.get("INTERIM_FONT_REGULAR", r"C:\Windows\Fonts\malgun.ttf"))
bold = Path(os.environ.get("INTERIM_FONT_BOLD", r"C:\Windows\Fonts\malgunbd.ttf"))
if not regular.exists() or not bold.exists():
    raise RuntimeError("한글 TTF 글꼴 경로를 INTERIM_FONT_REGULAR 및 INTERIM_FONT_BOLD로 지정하세요.")
pdfmetrics.registerFont(TTFont("InterimKorean", str(regular)))
pdfmetrics.registerFont(TTFont("InterimKoreanBold", str(bold)))
pdfmetrics.registerFontFamily(
    "InterimKorean", normal="InterimKorean", bold="InterimKoreanBold",
    italic="InterimKorean", boldItalic="InterimKoreanBold"
)

styles = getSampleStyleSheet()
definitions = {
    "ReportTitle": dict(fontName="InterimKoreanBold", fontSize=16.2, leading=22, spaceAfter=4),
    "ReportSubtitle": dict(fontName="InterimKoreanBold", fontSize=11.8, leading=17.2, spaceAfter=5),
    "ReportMeta": dict(fontName="InterimKorean", fontSize=8.8, leading=13.2, spaceAfter=5),
    "ReportHeading": dict(fontName="InterimKoreanBold", fontSize=11.4, leading=16.0,
                          spaceBefore=5.5, spaceAfter=3.5, keepWithNext=True),
    "ReportBody": dict(fontName="InterimKorean", fontSize=10.15, leading=15.2, spaceAfter=3.1),
    "ReportSmall": dict(fontName="InterimKorean", fontSize=8.8, leading=12.7, spaceAfter=3),
    "ReportCell": dict(fontName="InterimKorean", fontSize=8.8, leading=12.7),
    "ReportCellHead": dict(fontName="InterimKoreanBold", fontSize=8.8, leading=12.7),
    "AppendixTitle": dict(fontName="InterimKoreanBold", fontSize=14, leading=19, spaceAfter=3),
    "AppendixHeading": dict(fontName="InterimKoreanBold", fontSize=10.8, leading=14.4,
                            spaceBefore=4, spaceAfter=2, keepWithNext=True),
    "AppendixCaption": dict(fontName="InterimKorean", fontSize=8.7, leading=12.5, spaceAfter=3),
}
for name, settings in definitions.items():
    styles.add(ParagraphStyle(name=name, textColor=colors.black, wordWrap="CJK", **settings))


def p(text: str, style: str = "ReportBody") -> Paragraph:
    return Paragraph(text, styles[style])


def h(text: str) -> Paragraph:
    return p(text, "ReportHeading")


def ah(text: str) -> Paragraph:
    return p(text, "AppendixHeading")


def table(rows: list[list[object]], widths: list[float]) -> Table:
    data = [
        [p(escape(str(cell)), "ReportCellHead" if i == 0 else "ReportCell") for cell in row]
        for i, row in enumerate(rows)
    ]
    obj = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    obj.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 0.55, colors.black),
        ("LINEBELOW", (0, 0), (-1, 0), 0.45, colors.black),
        ("LINEBELOW", (0, -1), (-1, -1), 0.55, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
    ]))
    return obj


def image_flow(path: Path, width: float = 168 * mm) -> Image:
    result = Image(str(path))
    result.drawWidth = width
    result.drawHeight = result.imageHeight * width / result.imageWidth
    result.hAlign = "CENTER"
    return result


class TopScreen(Flowable):
    """Show the command and output area of the actual screenshot."""
    def __init__(self, path: Path, width: float = 168 * mm, left: int = 220,
                 right: int = 1200, top: int = 285):
        super().__init__()
        self.path = str(path)
        self.px_width, self.px_height = ImageReader(self.path).getSize()
        self.left, self.right, self.top = left, min(right, self.px_width), min(top, self.px_height)
        self.width = width
        self.scale = width / (self.right - self.left)
        self.height = self.top * self.scale

    def draw(self):
        clip = self.canv.beginPath()
        clip.rect(0, 0, self.width, self.height)
        self.canv.saveState()
        self.canv.clipPath(clip, stroke=0, fill=0)
        self.canv.drawImage(
            self.path, -self.left * self.scale, -(self.px_height - self.top) * self.scale,
            width=self.px_width * self.scale, height=self.px_height * self.scale
        )
        self.canv.restoreState()


def interim_chart() -> Drawing:
    """Profiles are grouped by daily rainfall record, not hourly exposure."""
    drawing = Drawing(492, 164)
    lines = [
        ("Rain >=0.1 mm", "0.1mm 이상", None),
        ("Recorded 0.0 mm", "0.0mm 기록", [5, 2]),
        ("Blank: dry candidate (unconfirmed)", "미확인 후보", [1, 2]),
    ]
    for i, (_, label, dash) in enumerate(lines):
        x = 89 + i * 128
        drawing.add(Line(x, 149, x + 19, 149, strokeColor=colors.black, strokeWidth=1,
                         strokeDashArray=dash))
        drawing.add(String(x + 23, 146, label, fontName="InterimKorean", fontSize=8.2,
                           fillColor=colors.black))
    drawing.add(String(0, 131, "승차(만 건)", fontName="InterimKorean", fontSize=7.8,
                       fillColor=colors.black))
    for weekend, label, x0 in [(False, "평일", 52), (True, "주말", 286)]:
        x1, y0, y1 = x0 + 190, 28, 123
        drawing.add(String(x0 + 83, 131, label, fontName="InterimKoreanBold", fontSize=8.7,
                           fillColor=colors.black))
        drawing.add(Line(x0, y0, x1, y0, strokeColor=colors.black, strokeWidth=.6))
        drawing.add(Line(x0, y0, x0, y1, strokeColor=colors.black, strokeWidth=.6))
        for value in [0, 20, 40, 60]:
            y = y0 + value / 60 * (y1 - y0)
            drawing.add(Line(x0 - 3, y, x0, y, strokeColor=colors.black, strokeWidth=.5))
            if not weekend:
                drawing.add(String(x0 - 19, y - 3, str(value), fontName="InterimKorean",
                                   fontSize=7.2, fillColor=colors.black))
        for hour in [6, 9, 12, 15, 18, 21]:
            x = x0 + (hour - 6) / 17 * (x1 - x0)
            drawing.add(String(x - 5, 14, f"{hour:02d}", fontName="InterimKorean",
                               fontSize=7.2, fillColor=colors.black))
        for key, _, dash in lines:
            part = [row for row in profiles if row["analysis_group"] == key
                    and (row["weekend"] == "True") == weekend]
            part.sort(key=lambda row: int(row["time_band"][:2]))
            points = []
            for row in part:
                hour = int(row["time_band"][:2])
                value = float(row["mean_boardings"])
                points.extend([x0 + (hour - 6) / 17 * (x1 - x0),
                               y0 + value / 600000 * (y1 - y0)])
            drawing.add(PolyLine(points, strokeColor=colors.black, strokeWidth=1,
                                 strokeDashArray=dash, fillColor=None))
    return drawing


def fmt(n: object) -> str:
    return f"{float(n):,.0f}"


def seasonal_row(season: str, day_type: str) -> dict[str, str]:
    return next(r for r in seasonal if r["season"] == season and r["day_type"] == day_type)


def period_row(period: str, band: str) -> dict[str, str]:
    return next(r for r in periods if r["period"] == period and r["rain_band"] == band)


def right_text(drawing: Drawing, right: float, y: float, text: str, size: float = 8) -> None:
    width = pdfmetrics.stringWidth(text, "InterimKorean", size)
    drawing.add(String(right - width, y, text, fontName="InterimKorean", fontSize=size,
                       fillColor=colors.black))


def center_text(drawing: Drawing, center: float, y: float, text: str, size: float = 8,
                font: str = "InterimKorean") -> None:
    width = pdfmetrics.stringWidth(text, font, size)
    drawing.add(String(center - width / 2, y, text, fontName=font, fontSize=size,
                       fillColor=colors.black))


def seasonal_difference_chart() -> Drawing:
    """Compare existing daily-record group means; samples are reported in table 5."""
    drawing = Drawing(492, 145)
    drawing.add(String(2, 133, "후보일 대비 강수 기록일의 일평균 승차 차이 (%)",
                       fontName="InterimKorean", fontSize=8.5, fillColor=colors.black))
    seasons = [("spring", "봄"), ("summer", "여름"), ("autumn", "가을"), ("winter", "겨울")]
    for day_type, title, x0, shade in [("weekday", "평일 (공휴일 포함)", 38, 0.35),
                                       ("weekend", "주말", 288, 0.58)]:
        x1 = x0 + 176
        center_text(drawing, (x0 + x1) / 2, 116, title, 8.6, "InterimKoreanBold")

        def position(value: float) -> float:
            return x0 + (value + 8) / 16 * (x1 - x0)

        for value in [-5, 0, 5]:
            x = position(value)
            drawing.add(Line(x, 21, x, 110,
                             strokeColor=colors.black if value == 0 else colors.lightgrey,
                             strokeWidth=0.65 if value == 0 else 0.4))
            center_text(drawing, x, 8, f"{value:+d}" if value else "0", 7.6)
        zero = position(0)
        for i, (season, label) in enumerate(seasons):
            y = 100 - i * 23
            value = float(seasonal_row(season, day_type)["rain_minus_candidate_pct"])
            assert -8 <= value <= 8
            x = position(value)
            right_text(drawing, x0 - 6, y - 2.5, label, 8.5)
            drawing.add(Rect(min(x, zero), y - 4.5, abs(x - zero), 9,
                             fillColor=colors.Color(shade, shade, shade),
                             strokeColor=colors.black, strokeWidth=0.35))
            label_value = f"{value:+.1f}%"
            if value < 0:
                right_text(drawing, x - 3, y - 2.6, label_value, 7.6)
            else:
                drawing.add(String(x + 3, y - 2.6, label_value, fontName="InterimKorean",
                                   fontSize=7.6, fillColor=colors.black))
    return drawing


def period_difference_chart() -> Drawing:
    """Bars show existing unadjusted differences grouped by daily rainfall."""
    drawing = Drawing(492, 155)
    series = [("0.1_to_lt5", "0.1-5mm 미만", 0.78),
              ("5_to_lt20", "5-20mm 미만", 0.50),
              ("at_least_20", "20mm 이상", 0.23)]
    for i, (_, label, shade) in enumerate(series):
        x = 7 + i * 151
        drawing.add(Rect(x, 141, 10, 7, fillColor=colors.Color(shade, shade, shade),
                         strokeColor=colors.black, strokeWidth=0.35))
        drawing.add(String(x + 14, 141, label, fontName="InterimKorean", fontSize=8.0,
                           fillColor=colors.black))

    x0, x1 = 111, 463
    for value in [-10, -5, 0]:
        x = x0 + (value + 10) / 10 * (x1 - x0)
        drawing.add(Line(x, 24, x, 134, strokeColor=colors.black if value == 0 else colors.lightgrey,
                         strokeWidth=0.65 if value == 0 else 0.4))
        center_text(drawing, x, 12, str(value), 7.8)
    for y, period, label in [(121, "morning", "출근 07-09시"),
                              (82, "midday", "낮 12-14시"),
                              (43, "evening", "퇴근 17-19시")]:
        right_text(drawing, x0 - 10, y - 2.5, label, 8.5)
        for offset, (key, _, shade) in zip([9, 0, -9], series):
            value = float(period_row(period, key)["difference_pct"])
            assert -10 <= value <= 0
            x = x0 + (value + 10) / 10 * (x1 - x0)
            bar_y = y + offset
            drawing.add(Rect(x, bar_y - 3.5, x1 - x, 7,
                             fillColor=colors.Color(shade, shade, shade),
                             strokeColor=colors.black, strokeWidth=0.35))
            right_text(drawing, x - 4, bar_y - 2.5, f"{value:+.1f}%", 7.4)
    return drawing


source_rows = [["연도", "원본 행", "완전 빈 행", "유효 행", "관측일", "역·호선 코드"]]
for row in year_audit:
    source_rows.append([
        row["year"], fmt(row["raw_rows"]), fmt(row["fully_empty_rows"]),
        fmt(row["valid_rows"]), row["observed_dates"], row["station_line_code_pairs"]
    ])

group_rows = [["요일", "일강수 기록", "고유 날짜", "평균 승차", "중앙값"]]
for weekend, label in [(False, "평일"), (True, "주말")]:
    for key, group in [
        ("Blank: dry candidate (unconfirmed)", "미확인 무강수 후보"),
        ("Rain >=0.1 mm", "0.1mm 이상"),
        ("Recorded 0.0 mm", "0.0mm 기록"),
    ]:
        row = next(r for r in daily_groups if r["analysis_group"] == key
                   and (r["weekend"] == "True") == weekend)
        group_rows.append([label, group, row["days"], fmt(row["mean_boardings"]),
                           fmt(row["median_boardings"])])

intensity_rows = [["일강수량", "평일 날짜", "평일 평균 승차", "주말 날짜", "주말 평균 승차"]]
for key, label in [("0.1 to <5 mm", "0.1-5mm 미만"),
                   ("5 to <20 mm", "5-20mm 미만"),
                   (">=20 mm", "20mm 이상")]:
    weekday = next(r for r in daily_intensity if r["intensity"] == key and r["weekend"] == "False")
    weekend = next(r for r in daily_intensity if r["intensity"] == key and r["weekend"] == "True")
    intensity_rows.append([label, weekday["days"], fmt(weekday["mean_boardings"]),
                           weekend["days"], fmt(weekend["mean_boardings"])])

season_rows = [["계절", "요일", "후보 일수", "강수 일수", "후보 평균", "강수 평균", "차이"]]
for season, label in [("spring", "봄"), ("summer", "여름"), ("autumn", "가을"), ("winter", "겨울")]:
    for day_type, day_label in [("weekday", "평일"), ("weekend", "주말")]:
        row = seasonal_row(season, day_type)
        season_rows.append([label, day_label, fmt(row["days_candidate_unconfirmed"]),
                            fmt(row["days_rain_at_least_0.1"]), fmt(row["mean_candidate_unconfirmed"]),
                            fmt(row["mean_rain_at_least_0.1"]),
                            f"{float(row['rain_minus_candidate_pct']):+.1f}%"])

period_rows = [["평일 시간대", "후보 평균", "0.1-5mm", "5-20mm", "20mm 이상"]]
for period, label in [("morning", "출근 07-09"), ("midday", "낮 12-14"), ("evening", "퇴근 17-19")]:
    reference = period_row(period, "candidate_unconfirmed")
    values = [f"{float(period_row(period, band)['difference_pct']):+.1f}%" for band in
              ["0.1_to_lt5", "5_to_lt20", "at_least_20"]]
    period_rows.append([label, fmt(reference["mean"]), *values])

distribution_rows = [["요일", "일강수 구분", "일수", "제1사분위", "중앙값", "제3사분위"]]
for day_type, day_label in [("weekday", "평일"), ("weekend", "주말")]:
    for group, label in [("candidate_unconfirmed", "미확인 후보"), ("rain_at_least_0.1", "0.1mm 이상")]:
        row = next(r for r in distributions if r["day_type"] == day_type and r["group"] == group)
        distribution_rows.append([day_label, label, fmt(row["days"]), fmt(row["q25"]),
                                  fmt(row["median"]), fmt(row["q75"])])


story = [
    # 본문 1쪽
    p("2차 중간 보고서", "ReportTitle"),
    p("비가 오는 날, 서울 지하철 이용은 어떻게 달라지는가?", "ReportSubtitle"),
    p("이경석  |  LLM을 활용한 빅데이터 분석  |  기존 자료 점검: 2026-11-24 14:40  |  기초 탐색 보강: " + enriched_audit["run_time_kst"].replace("T", " ")[:16] + " KST", "ReportMeta"),
    h("1. 프로젝트 개요와 해결하려는 문제"),
    p("강수가 있는 날 서울 지하철 이용이 평소와 어떻게 달라지는지 살펴봅니다. 출근처럼 이동 필요성이 큰 시간과 낮처럼 이동 목적이 다양한 시간은 강수와 이용량의 관계가 다를 수 있습니다. 이에 같은 시간대의 강수 조건별 차이와 같은 강수 조건의 시간대별 차이를 단계적으로 확인하고자 합니다."),
    p("다른 교통수단으로의 이동이나 이동시간 조정은 가능한 설명이지만, 이 프로젝트의 자료에는 교통수단 선택이나 개인의 이동 목적이 없습니다. 지하철 승차 건수의 차이만으로 선호 변화나 강수의 인과 효과를 판단하지 않습니다."),
    p("<b>중간 확인 내용.</b> 3년 공통 역의 평일 승차 건수는 일강수 0.1mm 이상인 날짜에서 미확인 무강수 후보일보다 단순 평균이 약 4.0% 낮았습니다. 계절별·시간대별로 나누면 차이의 크기가 달랐으며, 평균과 중앙값의 비교 방향이 다른 집단도 있었습니다. 이는 아직 달력 조건을 세밀하게 맞추지 않은 기초 탐색입니다."),
    table([
        ["연구 질문", "2차에서 확인할 범위"],
        ["강수 기록에 따라 일별 이용량이 다른가?", "일강수 기록별 날짜 수와 승차 건수의 평균·중앙값을 살펴봅니다."],
        ["평일·주말과 시간대에 따라 패턴이 다른가?", "일강수 기록으로 구분한 날의 시간대별 패턴을 기초 탐색합니다."],
        ["같은 시간의 강수와 이용량은 관련되는가?", "시간자료의 확보와 결합 가능성을 점검하고 이후 분석을 계획합니다."],
    ], [77*mm, 97*mm]),
    h("2. 데이터 및 분석 환경"),
    table([
        ["구분", "확보 자료와 주요 항목"],
        ["지하철", "서울교통공사 관할 1-8호선의 2023-2025년 역·호선·날짜별 시간대 승차·하차 건수"],
        ["기상", "기상청 서울 ASOS 108번의 같은 기간 일자료와 시간자료. 강수량, 기온 및 강수 관련 보조 항목"],
        ["도구", "Python, pandas, Jupyter Notebook 및 GitHub Codespaces. 원자료·코드·결과표를 함께 보관"],
    ], [28*mm, 146*mm]),
    p("주 분석 대상은 3년 동안 매일 승차와 하차 기록이 확인된 272개 역·호선 코드의 06-24시 승차 건수입니다. 환승역은 호선별로 구분합니다. 승차 건수는 고유 이용자 수나 혼잡도를 뜻하지 않습니다."),
    p("지하철 원자료와 일자료는 2026-11-19에, 시간별 기상자료는 2026-11-24에 확보했습니다. 06시 이전과 24시 이후 구간은 수송일자와 실제 날짜의 관계가 불확실하여 주 분석에서 제외했습니다.", "ReportSmall"),
    table([
        ["항목", "단위와 분석상 의미"],
        ["date / time_band", "수송일자와 시간 구간. 주 분석은 06-24시의 1시간 단위"],
        ["line / station_code", "호선과 역번호. 환승역의 호선별 기록을 구분"],
        ["boardings", "시간 구간별 승차 건수. 개인 이용자 수는 아님"],
        ["rain_mm / rain_duration_hr / temp_c", "강수량(mm), 일 강수 계속시간(시간), 일평균 기온(℃)"],
    ], [64*mm, 110*mm]),
    p("자료 사전. 승하차 구분은 별도로 유지하고, 강수량의 빈칸과 0.0mm 기록은 구분했습니다.", "ReportSmall"),

    # 전처리 및 결합 검증
    h("3. 진행 현황: 전처리와 결합 검증"),
    p("연도별 지하철 파일을 읽고 날짜·호선·역번호·승하차 구분을 후보 고유키로 확인했습니다. 시간대가 여러 열로 나뉜 원자료는 시간대별 행으로 바꾸었습니다. 비교 기간에 따라 역 구성이 달라지는 영향을 줄이기 위해 전체 3년의 공통 역·호선 코드를 별도로 선정했습니다."),
    KeepTogether([
        table(source_rows, [17*mm, 29*mm, 25*mm, 29*mm, 20*mm, 54*mm]),
        p("표 1. 연도별 원자료 점검. 2025년의 완전히 빈 행 134개를 제외한 뒤 각 연도의 후보 고유키 중복은 0건이었습니다. 역·호선 코드 수는 연도별 제공 범위를 뜻하며, 세 연도 공통 범위는 272개입니다.", "ReportSmall"),
    ]),
    KeepTogether([p("변환 전후의 승차·하차 합계를 공통 역과 전체 역으로 나누어 대조했습니다. 아래 합계는 3년 원자료의 모든 시간 구간을 포함한 검증값입니다. 각 모집단을 중복해서 합산한 승객 수가 아니라 변환이 값을 보존했는지를 확인하는 수치입니다.")]),
    KeepTogether([
        table([
            ["검증 대상", "승하차", "변환 전", "변환 후"],
            ["공통 역·호선", "승차", "4,760,795,829", "4,760,795,829"],
            ["공통 역·호선", "하차", "4,765,057,461", "4,765,057,461"],
            ["전체 역·호선", "승차", "4,763,868,691", "4,763,868,691"],
            ["전체 역·호선", "하차", "4,767,784,597", "4,767,784,597"],
        ], [40*mm, 22*mm, 56*mm, 56*mm]),
        p("표 2. 시간대 열을 행으로 바꾸기 전후의 합계. 서울역 1호선 2023-01-01 06-07시 승차도 원자료와 변환 자료에서 각각 145건으로 직접 대조했습니다.", "ReportSmall"),
    ]),
    p("일별 기상자료는 날짜별 중복과 전체 기간의 누락을 확인한 뒤 날짜를 기준으로 지하철 집계와 결합했습니다. 기상 미매칭 날짜는 0일이었고 결합 전후 집계 행은 각각 87,680행으로 같았습니다. 이 행 수에는 공통 역과 전체 역, 승차와 하차 및 경계 시간 구간이 함께 포함됩니다."),
    p("한 날짜의 기상값이 여러 지하철 시간 행에 반복되는 것은 결합 방식에 따른 결과입니다. 따라서 반복된 일강수량을 다시 합산하지 않고, 강수 조건의 표본 크기는 행 수가 아닌 고유 날짜 수로 표시했습니다."),

    # 일별 기초 결과
    h("4. 주요 방법과 중간 결과: 일별 강수 기록"),
    p("일강수량 0.1mm 이상은 336일, 0.0mm 기록은 132일, 빈칸은 628일이었습니다. 빈칸을 0으로 바꾸지 않았습니다. 0.0mm 기록 132일 중 131일에는 강수 계속시간이 기록되어 있어 0.0mm를 확정 무강수로 취급하기도 어렵습니다."),
    p("빈칸 중 강수 계속시간과 기상 기사의 관련 항목에서 강수 기록을 찾지 못한 625일은 ‘미확인 무강수 후보’로 구분했습니다. 관측상 무강수라고 확정된 집단은 아닙니다. 나머지 빈칸 3일은 이 후보에 포함하지 않았습니다."),
    KeepTogether([
        table(group_rows, [19*mm, 55*mm, 22*mm, 38*mm, 40*mm]),
        p("표 3. 공통 272개 역·호선 코드의 날짜별 06-24시 승차 건수. 평일은 월-금이며 공휴일을 포함합니다. 각 날짜 수는 집단별 고유 날짜입니다.", "ReportSmall"),
    ]),
    p("예를 들어 평일의 일평균 승차 건수는 미확인 후보 455일에서 4,813,381건, 일강수 0.1mm 이상 230일에서 4,623,082건이었습니다. 주말의 두 집단은 각각 170일과 106일이었습니다. 평균과 중앙값이 다른 만큼 대표값 하나만으로 전체 분포를 판단하지 않았습니다."),
    KeepTogether([
        table(intensity_rows, [39*mm, 22*mm, 46*mm, 22*mm, 45*mm]),
        p("표 4. 일강수량의 강도 구간별 날짜 수와 일평균 승차 건수입니다. 0.1mm 이상인 날짜만 구간별로 나누었으며, 각 구간의 계절·공휴일 구성은 보정하지 않았습니다.", "ReportSmall"),
    ]),
    interim_chart(),
    p("그림 1. 일강수 기록으로 분류한 날의 시간대별 평균 승차 패턴. 그림의 강수 구분은 하루 전체 기록이며 해당 시간에 실제 비가 왔다는 뜻이 아닙니다.", "ReportSmall"),
    p("강수일의 평일·주말 및 계절 구성이 후보일과 다를 수 있고, 공휴일·행사·운행 변화도 단순 평균에 영향을 줄 수 있습니다. 따라서 표와 그림은 기초 탐색 결과이며 강수로 인한 변화나 다른 교통수단으로의 전환을 보여주지는 않습니다.", "ReportSmall"),

    h("4.1 계절과 평일·주말을 나눈 기초 비교"),
    p("봄은 3-5월, 여름은 6-8월, 가을은 9-11월, 겨울은 12-2월로 구분했습니다. 각 계절 안에서 평일과 주말을 나누고, 미확인 무강수 후보와 일강수 0.1mm 이상인 날짜의 일평균 승차를 비교했습니다. 차이는 100×(강수일 평균÷후보일 평균 - 1)로 계산했습니다."),
    KeepTogether([
        table(season_rows, [14*mm, 17*mm, 21*mm, 21*mm, 36*mm, 36*mm, 29*mm]),
        p("표 5. 날짜 수와 06-24시 일평균 승차 건수입니다. 평일에는 공휴일이 포함됩니다. 후보는 확정 무강수가 아니며, 0.0mm와 나머지 미확인 기록은 두 비교집단에서 제외했습니다.", "ReportSmall"),
    ]),
    p("평일 강수 기록일의 단순 평균은 후보일보다 봄 약 5.3%, 여름 약 1.2%, 가을 약 5.4%, 겨울 약 3.5% 낮았습니다. 주말에는 겨울 강수 기록일의 평균이 후보일보다 높게 나타나는 등 방향도 일정하지 않았습니다. 계절별로 나눈 비교이지만 같은 연도·월·요일·기온까지 맞춘 결과는 아니므로 차이의 원인은 판단할 수 없습니다."),
    KeepTogether([
        seasonal_difference_chart(),
        p("그림 2. 계절·요일 구분별로 미확인 후보일의 일평균 승차를 기준으로 계산한 강수 기록일의 차이(%). 집단별 날짜 수와 평균은 표 5에 표시했습니다. 후보일은 확정 무강수가 아닙니다.", "ReportSmall"),
    ]),

    h("4.2 일강수 강도별 출근·낮·퇴근 패턴"),
    p("평일의 07-09시, 12-14시, 17-19시 승차 건수를 각각 두 시간 합계로 만들었습니다. 모든 날짜에서 18개 시간대의 합계가 기존 일별 승차 합계와 같은지 확인한 뒤, 하루 전체 강수량 구간별로 각 시간대 평균을 비교했습니다."),
    KeepTogether([
        table(period_rows, [36*mm, 38*mm, 33*mm, 33*mm, 34*mm]),
        p("표 6. 후보일의 두 시간 평균 승차 건수와 후보일 대비 강수 구간별 단순 평균 차이입니다. 후보는 455일, 일강수 0.1-5mm 미만은 124일, 5-20mm 미만은 54일, 20mm 이상은 52일입니다. 구간의 강수량은 시간당이 아닌 하루 전체 강수량입니다.", "ReportSmall"),
    ]),
    KeepTogether([
        period_difference_chart(),
        p("그림 3. 평일 미확인 후보일의 시간대별 평균을 기준으로 계산한 차이(%). 막대는 일강수량의 구간을 뜻하며, 해당 시간에 실제 비가 왔는지를 보여주지 않습니다.", "ReportSmall"),
    ]),
    p("예를 들어 일강수 20mm 이상인 52일의 평균은 후보 455일보다 출근 약 3.5%, 낮 약 7.8%, 퇴근 약 4.7% 낮았습니다. 이는 서로 다른 날짜 집단의 단순 평균 차이이며 표본의 계절·공휴일·요일 구성이 다를 수 있습니다. 시간대 사이에 강수의 영향이 다르다고 결론 내릴 수는 없습니다."),

    h("4.3 평균과 분포의 차이"),
    p("평균이 일부 낮거나 높은 날짜의 영향을 받을 수 있어 각 집단의 중앙값과 제1·제3사분위를 함께 확인했습니다. 사분위수는 정렬한 날짜 중 각각 25%와 75%에 해당하는 지점으로, 가운데 절반의 분포 범위를 보여줍니다."),
    KeepTogether([
        table(distribution_rows, [17*mm, 36*mm, 17*mm, 35*mm, 35*mm, 34*mm]),
        p("표 7. 06-24시 일별 승차 건수의 분포입니다. 날짜별 집계값을 사용했으며, 평균·사분위수의 차이는 달력 조건을 통제한 결과가 아닙니다.", "ReportSmall"),
    ]),
    p("주말에는 강수 기록일의 평균이 후보일보다 다소 낮지만, 중앙값은 강수 기록일이 더 높았습니다. 한 가지 대표값만으로 모든 날짜의 패턴을 설명하기 어렵습니다. 각 집단에서 제1사분위보다 사분위 범위의 1.5배 이상 낮은 날짜는 평일 후보 27일과 평일 강수 기록 21일이었습니다. 이는 추가 확인을 위한 낮은 값의 기준이며 자료 오류나 운행 장애를 판정한 결과는 아닙니다."),

    # 시간자료와 정렬 검토
    h("5. 시간별 기상자료 확보와 진행 중 확인한 문제"),
    p("일강수량은 같은 날의 모든 시간대에 붙일 수 있지만 특정 시간의 강수 여부를 알려주지 않습니다. 이 한계를 보완하기 위해 서울 ASOS 108번의 시간자료를 추가로 확보했습니다. 2023년 8,760행, 2024년 8,784행, 2025년 8,760행으로 총 26,304행이며 시간 표기의 누락·중복은 확인되지 않았습니다."),
    KeepTogether([table([
        ["시간 강수량 기록", "행 수", "현재 처리"],
        ["빈칸", "23,110", "0으로 채우지 않고 의미를 추가 확인합니다."],
        ["0.0mm", "1,377", "빈칸과 구분해 별도 기록으로 유지합니다."],
        ["양의 값", "1,817", "시간 구간을 확인한 뒤 비교에 활용할 계획입니다."],
    ], [42*mm, 28*mm, 104*mm])]),
    p("시간 자료를 지하철의 1시간 구간과 연결하려면 표기 시각이 구간의 시작인지 종료인지 확인해야 합니다. 양의 일강수량이 관측된 336일을 대상으로 시간자료를 하루 단위로 합산해 두 가지 정렬을 대조했습니다."),
    KeepTogether([
        table([
            ["일별 합산 기준", "일자료와 일치", "해석"],
            ["표기 날짜 그대로 합산", "187 / 336일", "자정을 경계로 기록이 나뉘는 영향을 받습니다."],
            ["표기 시각을 구간 종료로 가정", "336 / 336일", "한 시간 앞 구간에 연결하는 가정과 부합합니다."],
        ], [60*mm, 31*mm, 83*mm]),
        p("표 8. 양의 일강수량이 있는 날짜에서 0.05mm 이내 일치 여부를 확인했습니다. 종료시각 가정을 지지하는 경험적 점검이며, 공식 정의의 독립 확인이나 빈칸의 의미 확인을 대체하지는 못합니다.", "ReportSmall"),
    ]),
    p("예를 들어 표기 시각을 종료시각으로 가정하면 08시 기상 기록을 07-08시 지하철 구간에 대응합니다. 이 가정은 최종 비교 전에 자료 설명과 계속 대조할 필요가 있습니다."),
    p("또한 11-3월의 강수량은 3시간 간격으로 기록되는 구간이 있어 1시간 이용량과 바로 비교하기 어렵습니다. 2025-12-31의 23-24시를 종료시각으로 맞추려면 다음 날 00시 자료가 필요한데, 확보 파일은 2025-12-31 23시까지입니다. 이후 시간별 비교에서는 이 경계 구간을 제외할 계획입니다."),

    # 한계, 계획, GPT 활용
    h("6. 문제점과 한계"),
    p("서울 관측소 한 지점의 강수 기록은 모든 역 주변의 날씨를 대표하지 못할 수 있습니다. 강수량 빈칸의 의미와 시간 표기의 공식 정의도 추가 확인이 필요합니다. 공휴일·행사·운행 장애·재택근무 등 이용량에 영향을 줄 수 있는 모든 요인을 현재 자료만으로 구분할 수 없습니다."),
    p("일강수로 나눈 시간대 그림은 ‘강수가 관측된 날의 이용 패턴’입니다. 실제 같은 시간의 강수와 이용을 비교한 결과로 표현하지 않습니다. 승차 건수에는 개인의 이동 목적이나 이용 교통수단이 없어 자차·버스·택시로의 전환과 그 이유를 확인할 수도 없습니다."),
    h("7. 향후 진행 계획"),
    table([
        ["단계", "남은 작업"],
        ["자료 조건 정리", "시간 구간과 빈칸 해석을 추가 확인하고, 4-10월 평일 중 공휴일을 확인해 제외합니다."],
        ["조건별 비교", "출근 07-09시, 낮 12-14시, 퇴근 17-19시를 1시간 단위로 나누고 시간 강수 0.1-3mm 미만 및 3mm 이상을 비교합니다."],
        ["유사 조건·불확실성", "같은 연월·요일·시간의 후보일과 비교하고 연월·요일·시간·기온을 고려합니다. 고유 날짜 수와 날짜별 반복 관측을 반영한 불확실성을 함께 제시합니다."],
        ["기준 점검", "미확인 후보와 0.0mm 기록을 구분해 비교 기준의 영향을 살피고 관찰된 연관성과 가능한 설명을 구별합니다."],
    ], [35*mm, 139*mm]),
    p("2차의 평일 기초표에는 공휴일이 포함됩니다. 이후 공휴일을 제외한 표본을 사용하면 두 결과의 대상이 달라지므로 직접 같은 집단으로 비교하지 않을 예정입니다.", "ReportSmall"),
    p("같은 강수 구간에서 시간대에 따른 관계가 다른지도 직접 비교할 계획입니다. 한 시간대의 결과만 통계적으로 뚜렷하다는 이유로 다른 시간대와 차이가 있다고 판단하지 않고, 강수 구간과 시간대의 관계를 함께 검토하겠습니다."),
    h("8. GPT 활용 및 결과 검증"),
    p("작성자는 연구 질문과 분석 범위를 정하고 GitHub·기상청 인증 및 기상자료 다운로드를 수행했습니다. GPT를 활용해 데이터 처리·기초 분석 코드와 보고서 초안을 작성하고 실행 결과를 점검했습니다. 생성된 코드의 결과는 원자료 직접 대조, 변환·결합 전후 합계와 결측 분류로 확인했습니다."),
    p("기존 중복 후보키·결측·미매칭·시간대 표기 검증 4개와 추가 분석의 강수 구간 경계·계절 및 시간대 정의·시간대 합산·분포 대조 검증 4개를 실행해 모두 통과했습니다. 추가 탐색은 기존 입력으로 2026-11-26 Codespaces에서 다시 수행했으며, 결과표와 실행 로그·화면을 별첨과 공개 저장소에 보관했습니다."),
    p("중복키·기상 미매칭 오류 감지도 시험했으나, 원자료의 모든 오류를 검증하지는 못합니다."),
    p('<link href="https://data.seoul.go.kr/dataList/OA-12921/F/1/datasetView.do" color="black">서울 열린데이터광장 OA-12921</link> · <link href="https://data.kma.go.kr/data/grnd/selectAsosRltmList.do?pgmNo=36" color="black">기상청 종관기상관측(ASOS)</link> · <link href="https://github.com/leeks2026/llm-data-analysis-study/tree/main/data-analysis-project/02_interim_report" color="black">2차 공개 GitHub 자료</link>', "ReportSmall"),
    PageBreak(),

    # 별첨 1쪽
    p("별첨", "AppendixTitle"),
    ah("1. 연도별 원자료와 표본 직접 대조"),
    p("2026-11-23 Codespaces 화면입니다. 유효 행, 빈 행, 후보키 중복과 서울역 원자료 대조 결과를 확인했습니다.", "AppendixCaption"),
    image_flow(CAPTURES / "01_source.jpg", 160*mm),
    ah("2. 시간대 변환과 날짜 결합"),
    p("공통 역과 전체 역의 변환 전후 승하차 합계, 미매칭 날짜와 결합 전후 행 수를 확인했습니다.", "AppendixCaption"),
    image_flow(CAPTURES / "02_join.jpg", 160*mm),
    ah("3. 일강수 기록과 보조 항목"),
    p("일강수량의 양의 값·0.0mm·빈칸과 강수 계속시간 기록을 구분한 화면입니다.", "AppendixCaption"),
    image_flow(CAPTURES / "03_precip.jpg", 160*mm),
    PageBreak(),

    # 별첨 2쪽
    ah("4. 평일·주말의 일별 기초 집계"),
    p("미확인 후보와 일강수량 0.1mm 이상 집단의 고유 날짜 수와 평균·중앙값을 확인했습니다.", "AppendixCaption"),
    image_flow(CAPTURES / "04_eda.jpg"),
    ah("5. 데이터 처리 코드 검증"),
    p("2026-11-23 실행 화면입니다. 중복·결측·미매칭·시간대 표기에 관한 4개 검증이 통과했습니다.", "AppendixCaption"),
    image_flow(CAPTURES / "05_tests.jpg"),
    ah("6. 시간별 원자료 및 시각 정렬 재확인"),
    p("아래는 중간 현황 기준 이후인 2026-11-24 15:16에 동일 입력을 다시 확인한 화면입니다. 시간자료 행 수와 일별 합산 점검만 제시합니다.", "AppendixCaption"),
    TopScreen(CAPTURES / "06_hourly_quality.jpg"),
    p("자료와 실행 기록: 공개 저장소의 notebooks/02_중간분석.ipynb, results/interim/ 및 scripts/에 원자료 처리 코드, 실행 결과표와 로그를 함께 보관했습니다.", "AppendixCaption"),
    PageBreak(),

    ah("7. 추가 기초 분석 실행"),
    p("2026-11-26 Codespaces에서 기존 자료를 이용해 계절·시간대·분포 분석을 실행한 화면입니다. 날짜별 18시간 합계가 일별 합계와 일치하는지 확인했습니다.", "AppendixCaption"),
    TopScreen(CAPTURES / "07_enriched_run.jpg", 166*mm, left=220, right=890, top=315),
    ah("8. 추가 분석 검증"),
    p("강수 구간의 경계, 계절과 시간대 정의, 두 시간 합계, 사분위수의 원자료 대조를 확인하는 4개 검증을 실행했습니다.", "AppendixCaption"),
    TopScreen(CAPTURES / "08_enriched_tests.jpg", 166*mm, left=220, right=890, top=390),
    PageBreak(),

    ah("9. 계절별 평일 비교 결과"),
    p("추가 분석에서 생성한 표를 다시 불러 확인한 실제 화면입니다. 비교 기준은 확정 무강수일이 아닌 미확인 후보일입니다.", "AppendixCaption"),
    TopScreen(CAPTURES / "09_enriched_season.jpg", 166*mm, left=220, right=890, top=305),
    ah("10. 시간대별 기초 비교 결과"),
    p("일강수량 구간으로 나눈 날의 두 시간 승차 합계를 확인했습니다. 같은 시간의 실제 강수 노출을 계산한 결과는 아닙니다.", "AppendixCaption"),
    TopScreen(CAPTURES / "10_enriched_period.jpg", 166*mm, left=220, right=890, top=435),
    p("추가 분석의 코드와 날짜별·집단별 결과표, 입력 해시, 실행 및 검증 로그는 공개 저장소의 scripts/, tests/와 results/interim/enriched_eda/에 보관했습니다.", "AppendixCaption"),
]


def footer(canvas, doc):
    canvas.setFillColor(colors.black)
    canvas.setFont("InterimKorean", 8)
    canvas.drawString(18*mm, 11.5*mm, "서울 강수와 지하철 이용 | 2차 중간 보고서")
    canvas.drawRightString(192*mm, 11.5*mm, str(doc.page))


SimpleDocTemplate(
    str(REPORT), pagesize=A4, leftMargin=18*mm, rightMargin=18*mm,
    topMargin=14*mm, bottomMargin=17*mm,
    title="2차 중간 보고서: 서울 강수와 지하철 이용", author="이경석"
).build(story, onFirstPage=footer, onLaterPages=footer)
print(REPORT)

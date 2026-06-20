"""
爬虫配置 —— cie.fraft.cn 网站结构定义

PDF 直链模式:
    https://cie.fraft.cn/obj/Common/Fetch/redir/{filename}.pdf

文件名命名规则:
    {subject}_{session}{year2}_{type}_{paper}{variant}.pdf
    例: 9709_s25_qp_31.pdf
        - subject: 9709 (Mathematics)
        - session: s (summer/May-June), w (winter/Oct-Nov), m (March)
        - year2:   25 (2025)
        - type:    qp (question paper), ms (mark scheme)
        - paper:   3 (Paper 3 = Pure Mathematics 3)
        - variant: 1

9709 Mathematics 试卷结构:
    Paper 1: Pure Mathematics 1 (AS)
    Paper 2: Pure Mathematics 2 (AS, 部分年份)
    Paper 3: Pure Mathematics 3 (A2)
    Paper 4: Mechanics (A2)
    Paper 5: Probability & Statistics 1 (AS)
    Paper 6: Probability & Statistics 2 (A2)
    Variants: 通常 1-3，偶尔到 5
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# 网站配置
# ---------------------------------------------------------------------------
BASE_URL = "https://cie.fraft.cn"
PDF_URL_TEMPLATE = f"{BASE_URL}/obj/Common/Fetch/redir/{{filename}}.pdf"

# ---------------------------------------------------------------------------
# 9709 Mathematics 特定配置
# ---------------------------------------------------------------------------
SUBJECT_CODE = "9709"

SESSIONS = ["s", "w", "m"]  # summer, winter, march
SESSION_NAMES = {"s": "夏季(May/Jun)", "w": "冬季(Oct/Nov)", "m": "春季(Feb/Mar)"}

# 年份范围 (2位数字)
YEAR_START = 15  # 2015
YEAR_END = 25    # 2025

# Paper 编号和对应名称
PAPERS = {
    1: "Pure Mathematics 1",
    2: "Pure Mathematics 2",
    3: "Pure Mathematics 3",
    4: "Mechanics",
    5: "Probability & Statistics 1",
    6: "Probability & Statistics 2",
}

# 每个 paper 的变体数 (保守估计，多试几个不影响)
MAX_VARIANTS = 5

# 文件类型
FILE_TYPES = ["qp", "ms"]  # question paper, mark scheme
FILE_TYPE_NAMES = {"qp": "Question Paper", "ms": "Mark Scheme"}

# ---------------------------------------------------------------------------
# 下载配置
# ---------------------------------------------------------------------------
DOWNLOAD_DIR = Path("data/papers")
CONCURRENCY = 1          # 最大并发下载数（服务器限速严格，用单线程）
REQUEST_DELAY = 2.5       # 请求间隔(秒)，避免被封
REQUEST_TIMEOUT = 30      # 单个请求超时(秒)
MAX_RETRIES = 3           # 最大重试次数
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


@dataclass
class PaperInfo:
    """一份试卷的元信息"""
    subject: str          # "9709"
    year: int             # 2025
    session: str          # "s", "w", "m"
    paper_num: int        # 1-6
    variant: int          # 1-5
    file_type: str        # "qp", "ms"

    @property
    def filename(self) -> str:
        """生成文件名 (不含 .pdf)"""
        year2 = str(self.year)[-2:]
        return f"{self.subject}_{self.session}{year2}_{self.file_type}_{self.paper_num}{self.variant}"

    @property
    def url(self) -> str:
        return PDF_URL_TEMPLATE.format(filename=self.filename)

    @property
    def local_path(self) -> Path:
        return DOWNLOAD_DIR / self.subject / str(self.year) / f"{self.filename}.pdf"

    @property
    def session_name(self) -> str:
        return SESSION_NAMES.get(self.session, self.session)

    @property
    def paper_name(self) -> str:
        return PAPERS.get(self.paper_num, f"Paper {self.paper_num}")

    @property
    def type_name(self) -> str:
        return FILE_TYPE_NAMES.get(self.file_type, self.file_type)

    def __str__(self) -> str:
        return f"{self.subject} {self.year} {self.session_name} {self.paper_name} V{self.variant} ({self.type_name})"


def generate_all_paper_infos(
    subject: str = SUBJECT_CODE,
    year_start: int = YEAR_START,
    year_end: int = YEAR_END,
    sessions: list[str] | None = None,
    papers: list[int] | None = None,
    file_types: list[str] | None = None,
) -> list[PaperInfo]:
    """生成所有可能的试卷组合列表"""
    sessions = sessions or SESSIONS
    papers = papers or list(PAPERS.keys())
    file_types = file_types or FILE_TYPES

    result = []
    for year2 in range(year_start, year_end + 1):
        year = 2000 + year2
        for session in sessions:
            for paper_num in papers:
                for variant in range(1, MAX_VARIANTS + 1):
                    for ft in file_types:
                        result.append(PaperInfo(
                            subject=subject,
                            year=year,
                            session=session,
                            paper_num=paper_num,
                            variant=variant,
                            file_type=ft,
                        ))
    return result

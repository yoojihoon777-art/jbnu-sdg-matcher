from __future__ import annotations

import argparse
import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Optional


# ============================================================
# 1. 기본 자료형
# ============================================================

FIELD_NAMES = {
    "TITLE",
    "TITLE-ABS",
    "AUTHKEY",
    "TITLE-ABS-KEY",
    "SUBJAREA",
}


class Truth(Enum):
    TRUE = "TRUE"
    FALSE = "FALSE"
    UNKNOWN = "UNKNOWN"

    def __bool__(self):
        if self is Truth.UNKNOWN:
            raise TypeError("UNKNOWN cannot be converted to bool.")
        return self is Truth.TRUE


def truth_or(a: Truth, b: Truth) -> Truth:
    if a is Truth.TRUE or b is Truth.TRUE:
        return Truth.TRUE
    if a is Truth.UNKNOWN or b is Truth.UNKNOWN:
        return Truth.UNKNOWN
    return Truth.FALSE


def truth_and(a: Truth, b: Truth) -> Truth:
    if a is Truth.FALSE or b is Truth.FALSE:
        return Truth.FALSE
    if a is Truth.UNKNOWN or b is Truth.UNKNOWN:
        return Truth.UNKNOWN
    return Truth.TRUE


def truth_not(a: Truth) -> Truth:
    if a is Truth.TRUE:
        return Truth.FALSE
    if a is Truth.FALSE:
        return Truth.TRUE
    return Truth.UNKNOWN


@dataclass(frozen=True)
class Token:
    kind: str
    value: Any
    pos: int


@dataclass(frozen=True)
class Node:
    kind: str
    value: Any = None
    children: tuple["Node", ...] = ()
    pos: int = 0


@dataclass(frozen=True)
class Span:
    field: str
    start_token: int
    end_token: int
    query: str
    matched_text: str

    @property
    def width(self) -> int:
        return self.end_token - self.start_token + 1


@dataclass
class EvalResult:
    truth: Truth
    spans: list[Span] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def matched(self) -> bool:
        return self.truth is Truth.TRUE


@dataclass
class Paper:
    title: Optional[str] = None
    abstract: Optional[str] = None
    keywords: Optional[str | list[str] | tuple[str, ...]] = None
    subject_area: Optional[str | list[str] | tuple[str, ...]] = None


# ============================================================
# 2. Lexer
#    - 따옴표/중괄호 안에서는 Boolean/근접연산자를 해석하지 않음
#    - AND / OR / NOT은 대소문자 무시
#    - W/n, PRE/n 지원
# ============================================================

def _is_wordish(ch: str) -> bool:
    return ch.isalnum() or ch == "_"


def _operator_at(text: str, i: int):
    """
    현재 위치가 실제 연산자 시작점이면 (kind, value, length)를 반환.
    예: A W/2 B 의 W/2는 연산자,
        "A w/2 B"의 w/2는 따옴표 토큰 내부이므로 여기까지 오지 않음,
        mitigat*OR 같은 문자열의 OR는 연산자로 보지 않음.
    """
    prox = re.match(r"(?i)(W|PRE)/(\d+)", text[i:])
    if prox:
        raw = prox.group(0)
        j = i + len(raw)
        prev_ok = i == 0 or not _is_wordish(text[i - 1])
        next_ok = j == len(text) or not _is_wordish(text[j])
        if prev_ok and next_ok:
            return "PROX", (prox.group(1).upper(), int(prox.group(2))), len(raw)

    for word in ("AND", "NOT", "OR"):
        n = len(word)
        if text[i:i + n].upper() != word:
            continue

        j = i + n

        # 실제 연산자는 보통 공백/괄호/인용부호 경계에 있다.
        # '*' 뒤의 OR처럼 검색어 자체에 붙어 있는 문자열은 제외한다.
        prev_ok = (
            i == 0
            or text[i - 1].isspace()
            or text[i - 1] in ')("{'
        )
        next_ok = (
            j == len(text)
            or text[j].isspace()
            or text[j] in '()"{'
        )

        if prev_ok and next_ok:
            return word, word, n

    return None


def lex(text: str) -> list[Token]:
    tokens: list[Token] = []
    i = 0
    n = len(text)

    while i < n:
        ch = text[i]

        if ch.isspace():
            i += 1
            continue

        if ch == "(":
            tokens.append(Token("LPAREN", ch, i))
            i += 1
            continue

        if ch == ")":
            tokens.append(Token("RPAREN", ch, i))
            i += 1
            continue

        # "..." : loose/approximate phrase
        if ch == '"':
            start = i
            i += 1
            buf = []
            while i < n and text[i] != '"':
                buf.append(text[i])
                i += 1
            if i >= n:
                raise SyntaxError(f'닫히지 않은 큰따옴표: 위치 {start}')
            i += 1
            tokens.append(Token("PHRASE", "".join(buf), start))
            continue

        # {...} : exact phrase
        if ch == "{":
            start = i
            i += 1
            buf = []
            while i < n and text[i] != "}":
                buf.append(text[i])
                i += 1
            if i >= n:
                raise SyntaxError(f"닫히지 않은 중괄호: 위치 {start}")
            i += 1
            tokens.append(Token("EXACT", "".join(buf), start))
            continue

        op = _operator_at(text, i)
        if op:
            kind, value, length = op
            tokens.append(Token(kind, value, i))
            i += length
            continue

        # BARE:
        # 예: TITLE-ABS(underbanked), SUBJAREA(AGRI),
        #     TITLE-ABS-KEY(pes scheme*), TITLE-ABS(cereal*)
        start = i
        while i < n:
            if text[i] in '()"{':
                break
            if _operator_at(text, i):
                break
            i += 1

        raw = text[start:i].strip()
        if raw:
            upper = raw.upper()
            kind = "FIELD" if upper in FIELD_NAMES else "BARE"
            value = upper if kind == "FIELD" else raw
            tokens.append(Token(kind, value, start))
        else:
            # 무한루프 방지
            i += 1

    tokens.append(Token("EOF", None, n))
    return tokens


# ============================================================
# 3. Parser
#
# Scopus 연산자 우선순위
#   1) OR
#   2) W/n, PRE/n
#   3) AND
#   4) AND NOT
#
# 숫자가 작을수록 먼저 계산되므로,
# 재귀하강 파서에서는 OR를 가장 안쪽에서 파싱한다.
# ============================================================

class ParseError(SyntaxError):
    pass


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.i = 0

    def peek(self, offset: int = 0) -> Token:
        return self.tokens[min(self.i + offset, len(self.tokens) - 1)]

    def eat(self, kind: Optional[str] = None) -> Token:
        tok = self.peek()
        if kind is not None and tok.kind != kind:
            raise ParseError(
                f"{kind}가 필요하지만 {tok.kind}({tok.value!r})가 발견됨 "
                f"[문자 위치 {tok.pos}]"
            )
        self.i += 1
        return tok

    def parse(self) -> Node:
        node = self.parse_and_not()
        if self.peek().kind != "EOF":
            tok = self.peek()
            raise ParseError(
                f"예상하지 못한 토큰 {tok.kind}({tok.value!r}) "
                f"[문자 위치 {tok.pos}]"
            )
        return node

    # 가장 낮은 우선순위
    def parse_and_not(self) -> Node:
        left = self.parse_and()

        while self.peek().kind == "AND" and self.peek(1).kind == "NOT":
            pos = self.eat("AND").pos
            self.eat("NOT")
            right = self.parse_and()
            left = Node("AND_NOT", children=(left, right), pos=pos)

        return left

    def parse_and(self) -> Node:
        first = self.parse_proximity()
        parts = [first]
        first_pos = first.pos

        while self.peek().kind == "AND" and self.peek(1).kind != "NOT":
            self.eat("AND")
            parts.append(self.parse_proximity())

        if len(parts) == 1:
            return first
        return Node("AND", children=tuple(parts), pos=first_pos)

    def parse_proximity(self) -> Node:
        left = self.parse_or()

        while self.peek().kind == "PROX":
            tok = self.eat("PROX")
            right = self.parse_or()
            left = Node(
                "PROX",
                value=tok.value,   # ("W"|"PRE", n)
                children=(left, right),
                pos=tok.pos,
            )

        return left

    # 가장 높은 Boolean 우선순위
    def parse_or(self) -> Node:
        first = self.parse_primary()
        parts = [first]
        first_pos = first.pos

        while self.peek().kind == "OR":
            self.eat("OR")
            parts.append(self.parse_primary())

        if len(parts) == 1:
            return first
        return Node("OR", children=tuple(parts), pos=first_pos)

    def parse_primary(self) -> Node:
        tok = self.peek()

        if tok.kind == "LPAREN":
            pos = self.eat("LPAREN").pos
            inner = self.parse_and_not()
            self.eat("RPAREN")
            return Node("GROUP", children=(inner,), pos=pos)

        if tok.kind == "FIELD":
            field_tok = self.eat("FIELD")
            self.eat("LPAREN")
            inner = self.parse_and_not()
            self.eat("RPAREN")
            return Node(
                "FIELD",
                value=field_tok.value,
                children=(inner,),
                pos=field_tok.pos,
            )

        if tok.kind in {"PHRASE", "EXACT", "BARE"}:
            self.eat()
            return Node(tok.kind, value=tok.value, pos=tok.pos)

        raise ParseError(
            f"검색어나 괄호가 필요하지만 {tok.kind}({tok.value!r})가 발견됨 "
            f"[문자 위치 {tok.pos}]"
        )


def parse_query(text: str) -> Node:
    return Parser(lex(text)).parse()


@lru_cache(maxsize=64)
def parse_query_file(path: str) -> Node:
    text = Path(path).read_text(encoding="utf-8-sig")
    return parse_query(text)


# ============================================================
# 4. 논문 텍스트 인덱스
# ============================================================

@dataclass
class IndexedText:
    original: str
    folded: str
    tokens: list[str]
    token_char_spans: list[tuple[int, int]]

    @classmethod
    def build(cls, text: str) -> "IndexedText":
        original = unicodedata.normalize("NFKC", text or "")
        folded = original.casefold()

        tokens = []
        spans = []

        # 문장부호는 loose phrase 검색에서 단어 경계로 취급
        for m in re.finditer(r"\w+", folded, flags=re.UNICODE):
            tokens.append(m.group(0))
            spans.append((m.start(), m.end()))

        return cls(original, folded, tokens, spans)

    def token_slice_text(self, start: int, end: int) -> str:
        if not self.token_char_spans or start < 0 or end >= len(self.token_char_spans):
            return ""
        a = self.token_char_spans[start][0]
        b = self.token_char_spans[end][1]
        return self.original[a:b]


def _coerce_text(value) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return " ; ".join(str(x) for x in value)
    return str(value)


class PaperIndex:
    def __init__(self, paper: Paper):
        raw = {
            "title": _coerce_text(paper.title),
            "abstract": _coerce_text(paper.abstract),
            "keywords": _coerce_text(paper.keywords),
            "subject_area": _coerce_text(paper.subject_area),
        }

        self.available = {k: (v is not None and v.strip() != "") for k, v in raw.items()}
        self.data = {
            k: IndexedText.build(v or "")
            for k, v in raw.items()
        }


FIELD_COMPONENTS = {
    "TITLE": ("title",),
    "TITLE-ABS": ("title", "abstract"),
    "AUTHKEY": ("keywords",),
    "TITLE-ABS-KEY": ("title", "abstract", "keywords"),
    "SUBJAREA": ("subject_area",),
}


# ============================================================
# 5. 검색어 매칭
# ============================================================

def _query_tokens(term: str) -> list[str]:
    """
    loose phrase용 토큰.
    *, ?는 wildcard이므로 남겨 둔다.
    하이픈 등 문장부호는 단어 경계로 취급한다.
    """
    term = unicodedata.normalize("NFKC", term).casefold()
    return re.findall(r"[\w*?]+", term, flags=re.UNICODE)


@lru_cache(maxsize=20000)
def _compile_token_pattern(token_pattern: str):
    out = []
    for ch in token_pattern:
        if ch == "*":
            out.append(".*")
        elif ch == "?":
            out.append(".")
        else:
            out.append(re.escape(ch))
    return re.compile("^" + "".join(out) + "$", flags=re.IGNORECASE)


def _match_loose_term(
    indexed: IndexedText,
    query: str,
    field_name: str,
) -> list[Span]:
    qtokens = _query_tokens(query)
    if not qtokens:
        return []

    patterns = [_compile_token_pattern(q) for q in qtokens]
    width = len(patterns)
    hits = []

    for start in range(0, len(indexed.tokens) - width + 1):
        ok = True
        for j, pat in enumerate(patterns):
            if pat.fullmatch(indexed.tokens[start + j]) is None:
                ok = False
                break
        if ok:
            end = start + width - 1
            hits.append(
                Span(
                    field=field_name,
                    start_token=start,
                    end_token=end,
                    query=query,
                    matched_text=indexed.token_slice_text(start, end),
                )
            )

    return hits


def _match_exact_term(
    indexed: IndexedText,
    query: str,
    field_name: str,
) -> list[Span]:
    """
    {...} exact phrase:
    우선 NFKC + casefold 후 문자 그대로 부분문자열 매칭.
    punctuation/space도 query에 적힌 그대로 유지한다.
    """
    q = unicodedata.normalize("NFKC", query).casefold()
    if not q:
        return []

    hits = []
    start_char = 0

    while True:
        pos = indexed.folded.find(q, start_char)
        if pos < 0:
            break

        end_char = pos + len(q)

        covered = [
            idx
            for idx, (a, b) in enumerate(indexed.token_char_spans)
            if not (b <= pos or a >= end_char)
        ]

        if covered:
            s = covered[0]
            e = covered[-1]
            hits.append(
                Span(
                    field=field_name,
                    start_token=s,
                    end_token=e,
                    query="{" + query + "}",
                    matched_text=indexed.original[pos:end_char],
                )
            )

        start_char = pos + max(1, len(q))

    return hits


# ============================================================
# 6. Evaluator
# ============================================================

def _dedupe_spans(spans: Iterable[Span]) -> list[Span]:
    seen = set()
    out = []

    for s in spans:
        key = (
            s.field,
            s.start_token,
            s.end_token,
            s.query,
            s.matched_text,
        )
        if key not in seen:
            seen.add(key)
            out.append(s)

    return out


class Evaluator:
    def __init__(self, paper: Paper):
        self.paper = paper
        self.index = PaperIndex(paper)

        # (term kind, query, component) -> spans
        self.term_cache: dict[tuple[str, str, str], list[Span]] = {}

    def evaluate(self, node: Node) -> EvalResult:
        # 기본 context는 TITLE-ABS-KEY
        return self._eval(node, ("title", "abstract", "keywords"))

    def _eval(
        self,
        node: Node,
        components: tuple[str, ...],
    ) -> EvalResult:

        kind = node.kind

        if kind == "GROUP":
            return self._eval(node.children[0], components)

        if kind == "FIELD":
            new_components = FIELD_COMPONENTS[node.value]
            return self._eval(node.children[0], new_components)

        if kind in {"PHRASE", "BARE", "EXACT"}:
            return self._eval_term(kind, str(node.value), components)

        if kind == "OR":
            results = [self._eval(child, components) for child in node.children]

            truth = Truth.FALSE
            spans = []
            notes = []

            for result in results:
                truth = truth_or(truth, result.truth)
                if result.truth is Truth.TRUE:
                    spans.extend(result.spans)
                notes.extend(result.notes)

            return EvalResult(
                truth,
                _dedupe_spans(spans),
                notes,
            )

        if kind == "AND":
            results = [self._eval(child, components) for child in node.children]

            truth = Truth.TRUE
            notes = []
            for result in results:
                truth = truth_and(truth, result.truth)
                notes.extend(result.notes)

            spans = []
            if truth is Truth.TRUE:
                for result in results:
                    spans.extend(result.spans)

            return EvalResult(
                truth,
                _dedupe_spans(spans),
                notes,
            )

        if kind == "AND_NOT":
            left = self._eval(node.children[0], components)
            right = self._eval(node.children[1], components)

            truth = truth_and(left.truth, truth_not(right.truth))
            spans = left.spans if truth is Truth.TRUE else []

            notes = left.notes + right.notes
            if left.truth is Truth.TRUE and right.truth is Truth.TRUE:
                notes = notes + ["포함 조건은 충족했지만 AND NOT 제외 조건에도 일치함."]

            return EvalResult(
                truth,
                _dedupe_spans(spans),
                notes,
            )

        if kind == "PROX":
            left = self._eval(node.children[0], components)
            right = self._eval(node.children[1], components)
            op, n = node.value

            # 한쪽이 명확히 FALSE면 proximity도 FALSE
            if left.truth is Truth.FALSE or right.truth is Truth.FALSE:
                return EvalResult(
                    Truth.FALSE,
                    [],
                    left.notes + right.notes,
                )

            # 입력 누락으로 판정 불가
            if left.truth is Truth.UNKNOWN or right.truth is Truth.UNKNOWN:
                return EvalResult(
                    Truth.UNKNOWN,
                    [],
                    left.notes + right.notes,
                )

            pair_hits = self._proximity_hits(left.spans, right.spans, op, n)

            if pair_hits:
                return EvalResult(
                    Truth.TRUE,
                    pair_hits,
                    left.notes + right.notes,
                )

            return EvalResult(
                Truth.FALSE,
                [],
                left.notes + right.notes,
            )

        raise ValueError(f"지원하지 않는 AST 노드: {kind}")

    def _eval_term(
        self,
        term_kind: str,
        query: str,
        components: tuple[str, ...],
    ) -> EvalResult:
        all_hits: list[Span] = []
        missing_components = []

        for component in components:
            if not self.index.available[component]:
                missing_components.append(component)
                continue

            cache_key = (term_kind, query, component)

            if cache_key not in self.term_cache:
                indexed = self.index.data[component]

                if term_kind == "EXACT":
                    hits = _match_exact_term(indexed, query, component)
                else:
                    hits = _match_loose_term(indexed, query, component)

                self.term_cache[cache_key] = hits

            all_hits.extend(self.term_cache[cache_key])

        if all_hits:
            return EvalResult(
                Truth.TRUE,
                _dedupe_spans(all_hits),
                [],
            )

        if missing_components:
            readable = ", ".join(missing_components)
            return EvalResult(
                Truth.UNKNOWN,
                [],
                [f"입력되지 않은 검색 필드가 있어 판정 보류: {readable}"],
            )

        return EvalResult(Truth.FALSE, [], [])

    def _proximity_hits(
        self,
        left_spans: list[Span],
        right_spans: list[Span],
        op: str,
        n: int,
    ) -> list[Span]:
        """
        PRE/0 = 바로 인접.
        W/n   = 순서 무관, 두 span 사이에 있는 단어 수 <= n.
        PRE/n = 왼쪽 표현이 먼저 나오고, 사이 단어 수 <= n.
        """
        hits = []

        by_field_left: dict[str, list[Span]] = {}
        by_field_right: dict[str, list[Span]] = {}

        for s in left_spans:
            by_field_left.setdefault(s.field, []).append(s)
        for s in right_spans:
            by_field_right.setdefault(s.field, []).append(s)

        for field_name in set(by_field_left) & set(by_field_right):
            for a in by_field_left[field_name]:
                for b in by_field_right[field_name]:

                    if op == "PRE":
                        # 왼쪽이 실제로 먼저 있어야 함
                        if a.end_token >= b.start_token:
                            continue

                        gap = b.start_token - a.end_token - 1
                        if gap <= n:
                            hits.append(
                                self._merge_prox_span(a, b, f"PRE/{n}")
                            )

                    elif op == "W":
                        if a.end_token < b.start_token:
                            gap = b.start_token - a.end_token - 1
                        elif b.end_token < a.start_token:
                            gap = a.start_token - b.end_token - 1
                        else:
                            gap = 0

                        if gap <= n:
                            hits.append(
                                self._merge_prox_span(a, b, f"W/{n}")
                            )

                    else:
                        raise ValueError(f"알 수 없는 proximity operator: {op}")

        return _dedupe_spans(hits)

    def _merge_prox_span(
        self,
        a: Span,
        b: Span,
        operator: str,
    ) -> Span:
        field_name = a.field
        start = min(a.start_token, b.start_token)
        end = max(a.end_token, b.end_token)

        indexed = self.index.data[field_name]

        return Span(
            field=field_name,
            start_token=start,
            end_token=end,
            query=f"({a.query}) {operator} ({b.query})",
            matched_text=indexed.token_slice_text(start, end),
        )


# ============================================================
# 7. 편의 함수
# ============================================================

def evaluate_query(text: str, paper: Paper) -> EvalResult:
    ast = parse_query(text)
    return Evaluator(paper).evaluate(ast)


def evaluate_query_file(path: str | Path, paper: Paper) -> EvalResult:
    path = str(path)
    ast = parse_query_file(path)
    return Evaluator(paper).evaluate(ast)


def validate_query_files(folder: str | Path) -> list[dict[str, Any]]:
    folder = Path(folder)
    rows = []

    for i in range(1, 18):
        path = folder / f"SDG{i:02d}.txt"

        if not path.exists():
            rows.append(
                {
                    "sdg": i,
                    "file": str(path),
                    "status": "MISSING",
                    "tokens": None,
                    "error": "파일 없음",
                }
            )
            continue

        try:
            text = path.read_text(encoding="utf-8-sig")
            tokens = lex(text)
            Parser(tokens).parse()

            rows.append(
                {
                    "sdg": i,
                    "file": str(path),
                    "status": "OK",
                    "tokens": len(tokens) - 1,
                    "error": "",
                }
            )

        except Exception as exc:
            rows.append(
                {
                    "sdg": i,
                    "file": str(path),
                    "status": "ERROR",
                    "tokens": None,
                    "error": str(exc),
                }
            )

    return rows


def _cli():
    parser = argparse.ArgumentParser(
        description="Scopus SDG Boolean query parser/evaluator"
    )
    parser.add_argument(
        "--validate",
        metavar="QUERY_FOLDER",
        help="SDG01.txt~SDG17.txt가 있는 폴더의 검색식을 전부 파싱하여 검증",
    )
    args = parser.parse_args()

    if args.validate:
        rows = validate_query_files(args.validate)

        print("SDG | STATUS | TOKENS | FILE")
        print("-" * 80)

        for row in rows:
            print(
                f"{row['sdg']:>3} | "
                f"{row['status']:<7} | "
                f"{str(row['tokens']):>7} | "
                f"{row['file']}"
            )

            if row["error"]:
                print("    ERROR:", row["error"])

        ok = all(row["status"] == "OK" for row in rows)
        raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    _cli()


# ============================================================
# 8. SDG 포착 가이드라인 (부분충족 / 가장 가까운 검색경로)
# ============================================================

@dataclass(frozen=True)
class GuideItem:
    status: str
    query: str
    field: str
    matched_text: str = ""
    message: str = ""


@dataclass
class GuidePlan:
    cost: int
    matched_count: int
    label: str
    items: list[GuideItem] = field(default_factory=list)

    @property
    def missing_count(self) -> int:
        return sum(
            1 for item in self.items
            if item.status in {"미충족", "위치 불일치", "근접조건 미충족", "입력 확인 필요", "제외조건"}
        )


def _guide_field_label(components: tuple[str, ...]) -> str:
    mapping = {
        ("title",): "제목",
        ("title", "abstract"): "제목 또는 초록",
        ("keywords",): "저자키워드",
        ("title", "abstract", "keywords"): "제목·초록·저자키워드",
        ("subject_area",): "AGRI 학문분야",
    }
    return mapping.get(tuple(components), " / ".join(components))


def _guide_term_label(kind: str, query: str) -> str:
    if kind == "EXACT":
        return "{" + query + "}"
    return query


def _join_labels(parts: Iterable[str], sep: str = " + ") -> str:
    out = []
    for p in parts:
        p = (p or "").strip()
        if p and p not in out:
            out.append(p)
    return sep.join(out)


def _guide_plan_key(plan: GuidePlan):
    item_sig = tuple(
        (i.status, i.query, i.field, i.matched_text, i.message)
        for i in plan.items
    )
    return (plan.label, item_sig)


def _prune_guide_plans(plans: list[GuidePlan], top_k: int) -> list[GuidePlan]:
    unique = {}
    for p in plans:
        key = _guide_plan_key(p)
        old = unique.get(key)
        if old is None or (p.cost, -p.matched_count) < (old.cost, -old.matched_count):
            unique[key] = p

    ranked = sorted(
        unique.values(),
        key=lambda p: (
            p.cost,
            -p.matched_count,
            p.missing_count,
            len(p.items),
            len(p.label),
        ),
    )
    return ranked[:top_k]


class GuideBuilder:
    def __init__(self, paper: Paper, top_k: int = 3):
        self.evaluator = Evaluator(paper)
        self.index = self.evaluator.index
        self.top_k = max(1, int(top_k))
        self._plan_cache: dict[tuple[int, tuple[str, ...]], list[GuidePlan]] = {}
        self._eval_cache: dict[tuple[int, tuple[str, ...]], EvalResult] = {}

    def _eval(self, node: Node, components: tuple[str, ...]) -> EvalResult:
        key = (id(node), tuple(components))
        if key not in self._eval_cache:
            self._eval_cache[key] = self.evaluator._eval(node, components)
        return self._eval_cache[key]

    def plans(
        self,
        node: Node,
        components: tuple[str, ...] = ("title", "abstract", "keywords"),
    ) -> list[GuidePlan]:
        key = (id(node), tuple(components))
        if key in self._plan_cache:
            return self._plan_cache[key]

        result = self._plans_uncached(node, tuple(components))
        result = _prune_guide_plans(result, self.top_k)
        self._plan_cache[key] = result
        return result

    def _plans_uncached(
        self,
        node: Node,
        components: tuple[str, ...],
    ) -> list[GuidePlan]:
        kind = node.kind

        if kind == "GROUP":
            return self.plans(node.children[0], components)

        if kind == "FIELD":
            new_components = FIELD_COMPONENTS[node.value]
            return self.plans(node.children[0], new_components)

        if kind in {"PHRASE", "BARE", "EXACT"}:
            return [self._term_plan(kind, str(node.value), components)]

        if kind == "OR":
            candidates = []
            for child in node.children:
                candidates.extend(self.plans(child, components))
            return candidates

        if kind == "AND":
            combined = [GuidePlan(0, 0, "", [])]

            for child in node.children:
                child_plans = self.plans(child, components)
                next_round = []

                for base in combined:
                    for cp in child_plans:
                        next_round.append(
                            GuidePlan(
                                cost=base.cost + cp.cost,
                                matched_count=base.matched_count + cp.matched_count,
                                label=_join_labels([base.label, cp.label]),
                                items=base.items + cp.items,
                            )
                        )

                combined = _prune_guide_plans(next_round, self.top_k)

            return combined

        if kind == "AND_NOT":
            left_plans = self.plans(node.children[0], components)
            right_eval = self._eval(node.children[1], components)

            if right_eval.truth is Truth.FALSE:
                return left_plans

            if right_eval.truth is Truth.TRUE:
                blockers = []
                for span in right_eval.spans[:3]:
                    blockers.append(
                        GuideItem(
                            status="제외조건",
                            query=span.query,
                            field={
                                "title": "제목",
                                "abstract": "초록",
                                "keywords": "저자키워드",
                                "subject_area": "AGRI 학문분야",
                            }.get(span.field, span.field),
                            matched_text=span.matched_text,
                            message="이 표현이 AND NOT 제외조건에 포착됨",
                        )
                    )

                if not blockers:
                    blockers = [
                        GuideItem(
                            status="제외조건",
                            query="AND NOT 조건",
                            field=_guide_field_label(components),
                            message="제외조건이 충족되어 이 검색경로가 차단됨",
                        )
                    ]

                return [
                    GuidePlan(
                        cost=p.cost + 1,
                        matched_count=p.matched_count,
                        label=p.label,
                        items=p.items + blockers,
                    )
                    for p in left_plans
                ]

            # UNKNOWN
            return [
                GuidePlan(
                    cost=p.cost + 1,
                    matched_count=p.matched_count,
                    label=p.label,
                    items=p.items + [
                        GuideItem(
                            status="입력 확인 필요",
                            query="AND NOT 제외조건",
                            field=_guide_field_label(components),
                            message="입력되지 않은 필드 때문에 제외조건 충족 여부를 확정할 수 없음",
                        )
                    ],
                )
                for p in left_plans
            ]

        if kind == "PROX":
            op, n = node.value
            node_eval = self._eval(node, components)

            # 실제 proximity 조건이 이미 충족된 경우에는 그 조건 전체를 충족 항목 하나로 표시
            if node_eval.truth is Truth.TRUE:
                matched_text = ""
                if node_eval.spans:
                    matched_text = node_eval.spans[0].matched_text
                label = self._node_compact_label(node)
                return [
                    GuidePlan(
                        cost=0,
                        matched_count=1,
                        label=label,
                        items=[
                            GuideItem(
                                status="충족",
                                query=label,
                                field=_guide_field_label(components),
                                matched_text=matched_text,
                                message=f"{op}/{n} 근접조건 충족",
                            )
                        ],
                    )
                ]

            left_plans = self.plans(node.children[0], components)
            right_plans = self.plans(node.children[1], components)
            combined = []

            for lp in left_plans:
                for rp in right_plans:
                    cost = lp.cost + rp.cost
                    items = lp.items + rp.items
                    matched_count = lp.matched_count + rp.matched_count
                    label = f"{lp.label} {op}/{n} {rp.label}".strip()

                    # 양쪽 검색어는 이미 존재하지만 거리/순서만 틀린 경우
                    if lp.cost == 0 and rp.cost == 0:
                        cost += 1
                        items = items + [
                            GuideItem(
                                status="근접조건 미충족",
                                query=f"{op}/{n}",
                                field=_guide_field_label(components),
                                message=(
                                    f"양쪽 표현은 존재하지만 {op}/{n}의 "
                                    "거리 또는 순서 조건을 충족하지 않음"
                                ),
                            )
                        ]

                    combined.append(
                        GuidePlan(
                            cost=cost,
                            matched_count=matched_count,
                            label=label,
                            items=items,
                        )
                    )

            return combined

        raise ValueError(f"지원하지 않는 AST 노드: {kind}")

    def _term_plan(
        self,
        term_kind: str,
        query: str,
        components: tuple[str, ...],
    ) -> GuidePlan:
        eval_result = self.evaluator._eval_term(term_kind, query, components)
        label = _guide_term_label(term_kind, query)
        field_label = _guide_field_label(components)

        if eval_result.truth is Truth.TRUE:
            first = eval_result.spans[0] if eval_result.spans else None
            matched_text = first.matched_text if first else ""
            matched_field = field_label
            if first:
                matched_field = {
                    "title": "제목",
                    "abstract": "초록",
                    "keywords": "저자키워드",
                    "subject_area": "AGRI 학문분야",
                }.get(first.field, first.field)

            return GuidePlan(
                cost=0,
                matched_count=1,
                label=label,
                items=[
                    GuideItem(
                        status="충족",
                        query=label,
                        field=field_label,
                        matched_text=matched_text,
                        message=f"{matched_field}에서 발견",
                    )
                ],
            )

        # 필요한 필드가 아닌 다른 입력 위치에 동일 검색어가 있는지 확인
        wrong_hits = []
        all_components = ("title", "abstract", "keywords")
        for comp in all_components:
            if comp in components or not self.index.available.get(comp, False):
                continue

            indexed = self.index.data[comp]
            if term_kind == "EXACT":
                hits = _match_exact_term(indexed, query, comp)
            else:
                hits = _match_loose_term(indexed, query, comp)
            wrong_hits.extend(hits)

        if wrong_hits:
            first = wrong_hits[0]
            found_where = {
                "title": "제목",
                "abstract": "초록",
                "keywords": "저자키워드",
            }.get(first.field, first.field)

            return GuidePlan(
                cost=1,
                matched_count=1,
                label=label,
                items=[
                    GuideItem(
                        status="위치 불일치",
                        query=label,
                        field=field_label,
                        matched_text=first.matched_text,
                        message=f"{found_where}에는 있으나 검색식은 {field_label}에서의 출현을 요구",
                    )
                ],
            )

        if eval_result.truth is Truth.UNKNOWN:
            return GuidePlan(
                cost=1,
                matched_count=0,
                label=label,
                items=[
                    GuideItem(
                        status="입력 확인 필요",
                        query=label,
                        field=field_label,
                        message=f"{field_label} 입력이 없어 조건 충족 여부를 확인할 수 없음",
                    )
                ],
            )

        return GuidePlan(
            cost=1,
            matched_count=0,
            label=label,
            items=[
                GuideItem(
                    status="미충족",
                    query=label,
                    field=field_label,
                    message=f"{field_label}에서 검색어를 찾지 못함",
                )
            ],
        )

    def _node_compact_label(self, node: Node) -> str:
        kind = node.kind

        if kind == "GROUP":
            return self._node_compact_label(node.children[0])

        if kind == "FIELD":
            return self._node_compact_label(node.children[0])

        if kind in {"PHRASE", "BARE"}:
            return str(node.value)

        if kind == "EXACT":
            return "{" + str(node.value) + "}"

        if kind == "OR":
            return " / ".join(self._node_compact_label(c) for c in node.children[:5])

        if kind == "AND":
            return " + ".join(self._node_compact_label(c) for c in node.children[:5])

        if kind == "AND_NOT":
            return self._node_compact_label(node.children[0])

        if kind == "PROX":
            op, n = node.value
            return (
                f"{self._node_compact_label(node.children[0])} "
                f"{op}/{n} "
                f"{self._node_compact_label(node.children[1])}"
            )

        return kind


def guide_query(text: str, paper: Paper, top_k: int = 3) -> list[GuidePlan]:
    ast = parse_query(text)
    return GuideBuilder(paper, top_k=top_k).plans(ast)


def guide_query_file(
    path: str | Path,
    paper: Paper,
    top_k: int = 3,
) -> list[GuidePlan]:
    ast = parse_query_file(str(path))
    return GuideBuilder(paper, top_k=top_k).plans(ast)

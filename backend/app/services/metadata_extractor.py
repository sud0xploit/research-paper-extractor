import re
from collections.abc import Mapping

from app.schemas.metadata import ResearchPaperMetadata


DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)
ISSN_PATTERN = re.compile(r"\b(\d{4})[- ]?(\d{3}[\dX])\b", re.IGNORECASE)
ISSN_LABEL_PATTERN = re.compile(
    r"\b(print\s+issn|electronic\s+issn|online\s+issn|e-?issn|issn)\b\s*[:#]?\s*(.*)",
    re.IGNORECASE,
)
YEAR_PATTERN = re.compile(r"\b(19\d{2}|20\d{2})\b")
LABEL_PATTERN = re.compile(
    r"^(title|authors?|journal(?:\s+name)?|conference(?:\s+name)?|publisher|doi)\s*:\s*(.+)$",
    re.IGNORECASE,
)
AFFILIATION_PATTERN = re.compile(
    r"^\s*([¹²³⁴⁵⁶⁷⁸⁹⁰]+|\d{1,2})[\s.)]*\s*(.+)$"
)
SUPERSCRIPT_PATTERN = re.compile(r"[¹²³⁴⁵⁶⁷⁸⁹⁰]+")
SUPERSCRIPT_DIGITS = dict(zip("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789"))
AUTHOR_MARKER_PATTERN = re.compile(r"(?:\^?\d{1,2}|[¹²³⁴⁵⁶⁷⁸⁹⁰]+)(?=\s*(?:[,;&]|$))")
MONTHS = {
    month.casefold(): month
    for month in (
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    )
}
DATE_LABEL_PATTERN = re.compile(
    r"\b(publication\s+date|published(?:\s+online)?|online\s+publication|available\s+online|issue\s+date)\b\s*[:\-]?\s*(.*)",
    re.IGNORECASE,
)
DATE_EXCLUSION_PATTERN = re.compile(r"\b(received|revised|accepted|submitted)\b", re.IGNORECASE)
REFERENCE_HEADING_PATTERN = re.compile(
    r"^\s*(?:references|bibliography|works\s+cited)\s*:?\s*$", re.IGNORECASE
)
AFFILIATION_WORD_PATTERN = re.compile(
    r"\b(dept\.?|department|faculty|school|institute|university|college|academy|engineering|technology|management|laborator|hospital|centre|center)\b",
    re.IGNORECASE,
)
TITLE_STOP_PATTERN = re.compile(
    r"^(abstract|keywords?|introduction|references|contents|article\s+history|\w+\s+article|research\s+paper|publication(?:\s+field)?|journal(?:\s+name)?|conference(?:\s+name)?|department|institution|college|city|month\s*&\s*year|ugc|issn|doi)\b",
    re.IGNORECASE,
)
ARTICLE_TYPE_PATTERN = re.compile(
    r"^\s*(?:short communication|research paper|research article|original article|original research|review article|case report)\s*$",
    re.IGNORECASE,
)
CONFERENCE_MASTHEAD_PATTERN = re.compile(
    r"^\s*(?:(?:\d{4}\s+)?(?:\d+(?:st|nd|rd|th)?\s+)?IEEE\s+)?(?:(?:international|annual)\s+)?conference\b|^\s*\d+(?:st|nd|rd|th)\s+IEEE\s+(?:international\s+)?conference\b",
    re.IGNORECASE,
)
AUTHOR_MARKER_LINE_PATTERN = re.compile(r"[¹²³⁴⁵⁶⁷⁸⁹⁰]|\b[A-Z][A-Za-z.'-]+\d\b|\d\s*[·,;]")
CONTAINER_HEADER_PATTERN = re.compile(
    r"^(?:(?:the\s+)?(?:international\s+)?journal\s+of\b|proceedings\s+of\b|ieee\s+(?:transactions|journal|conference)\b|acm\s+transactions\b)",
    re.IGNORECASE,
)
NON_TITLE_PATTERN = re.compile(
    r"\b(issn|isbn|doi|copyright|received|revised|accepted|published|proceedings|volume\s+\d+|session|subject|signature|principal|internal|external)\b",
    re.IGNORECASE,
)


def normalize_doi(value: str | None) -> str | None:
    if not value:
        return None
    doi = value.strip()
    doi = re.sub(r"^(?:https?://)?(?:dx\.)?doi\.org/", "", doi, flags=re.IGNORECASE)
    doi = re.sub(r"^doi\s*:\s*", "", doi, flags=re.IGNORECASE)
    return doi.rstrip(".,;:)]}>") or None


def extract_doi(text: str) -> str | None:
    doi, _, _, _, _ = _doi(_page_lines(text)[0])
    return doi


def _page_lines(text: str | Mapping) -> list[list[str]]:
    if isinstance(text, Mapping):
        pages = text.get("cleaned_layout_page_texts") or text.get("layout_page_texts") or text.get("cleaned_page_texts") or text.get("page_texts") or [
            text.get("cleaned_text") or text.get("raw_text", "")
        ]
    else:
        pages = [text or ""]
    result = []
    in_references = False
    for page in pages:
        lines = [line.strip() for line in str(page).splitlines() if line.strip()]
        if in_references:
            result.append([])
            continue
        reference_index = next((index for index, line in enumerate(lines) if REFERENCE_HEADING_PATTERN.match(line)), None)
        if reference_index is not None:
            in_references = True
            lines = lines[:reference_index]
        result.append(lines)
    return result


def _evidence(text: str | None, page: int | None) -> dict | None:
    snippet = re.sub(r"\s+", " ", text or "").strip()
    if not snippet:
        return None
    return {"text": snippet[:320], "page": page}


def _evidence_page(pages: list[list[str]], evidence: str | None) -> int | None:
    if evidence is None:
        return None
    return next((page_number for page_number, lines in enumerate(pages, start=1) if evidence in lines), None)


def _field(lines: list[str], names: tuple[str, ...]) -> tuple[str | None, int | None]:
    pattern = re.compile(r"^\s*(?:" + "|".join(names) + r")\s*:\s*(.+)$", re.IGNORECASE)
    for index, line in enumerate(lines):
        match = pattern.match(line)
        if match:
            return match.group(1).strip(), index
    return None, None


def _title(lines: list[str]) -> tuple[str | None, int | None, float]:
    if (
        any(re.match(r"^\[(?:title|author|department|college|city)", line, re.IGNORECASE) for line in lines[:12])
        or any(re.search(r"\|\s*\d+\s*/\s*\d+\s*$", line) for line in lines[:20])
    ):
        return None, None, 0.0
    explicit, index = _field(lines[:35], ("title", "paper title", "article title"))
    if explicit:
        if re.search(r"^\[.*\]$|^title of (?:the )?research paper$", explicit, re.IGNORECASE):
            return None, None, 0.0
        title_lines = [explicit]
        last_index = index
        for line in lines[index + 1 : min(index + 5, len(lines))]:
            if ARTICLE_TYPE_PATTERN.match(line):
                continue
            if LABEL_PATTERN.match(line) or TITLE_STOP_PATTERN.match(line) or AFFILIATION_PATTERN.match(line):
                break
            if NON_TITLE_PATTERN.search(line) or CONFERENCE_MASTHEAD_PATTERN.match(line):
                continue
            if len(line.split()) < 2 or NON_TITLE_PATTERN.search(line):
                break
            title_lines.append(line)
            last_index += 1
        return " ".join(title_lines), last_index, 0.98

    article_type_index = next(
        (index for index, line in enumerate(lines[:20]) if ARTICLE_TYPE_PATTERN.match(line)),
        -1,
    )
    candidate_lines = lines[article_type_index + 1 : 30]
    start = next(
        (
            index + article_type_index + 1 for index, line in enumerate(candidate_lines)
            if len(line.split()) >= 3 and len(line) <= 220
            and not TITLE_STOP_PATTERN.match(line)
            and not LABEL_PATTERN.match(line)
            and not NON_TITLE_PATTERN.search(line)
            and not CONTAINER_HEADER_PATTERN.match(line)
            and not CONFERENCE_MASTHEAD_PATTERN.match(line)
            and not AFFILIATION_WORD_PATTERN.search(line)
            and "[" not in line and "]" not in line
            and not re.search(r"@|https?://", line, re.IGNORECASE)
        ),
        None,
    )
    if start is None:
        return None, None, 0.0

    title_lines = [lines[start]]
    last_title_index = start
    for line_index, line in enumerate(lines[start + 1 : min(start + 8, len(lines))], start + 1):
        tokens = line.replace("-", " ").split()
        is_name_line = (
            2 <= len(tokens) <= 5
            and any(any(character.islower() for character in token) for token in tokens)
            and all(re.fullmatch(r"(?:[A-Z][A-Za-z'’.-]*|[A-Z])", token) for token in tokens)
            and not re.search(r"\b(?:and|for|with|to|using|based|of)\b", line, re.IGNORECASE)
            and not (
                line_index + 1 < len(lines)
                and re.search(r"\d\s*[·,;]|[¹²³⁴⁵⁶⁷⁸⁹⁰]", lines[line_index + 1])
            )
        )
        is_marked_author_line = bool(AUTHOR_MARKER_LINE_PATTERN.search(line))
        if (
            TITLE_STOP_PATTERN.match(line) or LABEL_PATTERN.match(line)
            or ARTICLE_TYPE_PATTERN.match(line) or AFFILIATION_WORD_PATTERN.search(line)
            or is_marked_author_line or is_name_line or len(line.split()) < 2 or len(line) > 220
            or re.search(r"@|https?://", line, re.IGNORECASE)
        ):
            break
        if NON_TITLE_PATTERN.search(line) or CONFERENCE_MASTHEAD_PATTERN.match(line):
            continue
        if re.search(r"[/|→•]", line):
            break
        title_lines.append(line)
        last_title_index = line_index
    return " ".join(title_lines), last_title_index, 0.76 if len(title_lines) > 1 else 0.72


def _affiliation_entries(lines: list[str]) -> dict[str, tuple[str, int]]:
    entries = {}
    for index, line in enumerate(lines[:50]):
        match = AFFILIATION_PATTERN.match(line)
        if match and AFFILIATION_WORD_PATTERN.search(match.group(2)):
            markers = match.group(1)
            if markers.isascii() and markers.isdigit():
                key = markers
            else:
                key = "".join(SUPERSCRIPT_DIGITS[marker] for marker in markers)
            entries[key] = (match.group(2).strip(), index)
    return entries


def _split_author_line(value: str) -> list[str]:
    value = re.sub(r"\b(?:and)\b|&|;|·", "|", value, flags=re.IGNORECASE)
    # Commas separate names in the author block; affiliations are parsed separately.
    return [part.strip() for part in value.split("|") if part.strip()] if "|" in value else [part.strip() for part in value.split(",") if part.strip()]


def _extract_authors(
    lines: list[str],
    title_index: int | None = None,
    title: str | None = None,
    affiliation_context: list[str] | None = None,
) -> tuple[list[dict], str | None, float]:
    affiliation_context = affiliation_context or lines
    affiliations = _affiliation_entries(affiliation_context)
    author_text, author_index = _field(lines[:35], ("authors", "author"))
    if author_text is None and (
        any(re.match(r"^\[(?:title|author|department|college|city)", line, re.IGNORECASE) for line in lines[:12])
        or any(re.search(r"\|\s*\d+\s*/\s*\d+\s*$", line) for line in lines[:20])
    ):
        return [], None, 0.0
    affiliation_lines = [
        line for line in lines[:40]
        if AFFILIATION_WORD_PATTERN.search(line) and not TITLE_STOP_PATTERN.match(line)
    ]
    if author_text is None:
        start = title_index + 1 if title_index is not None else 0
        stop = next(
            (
                index for index, line in enumerate(lines[start + 1 : 100], start + 1)
                if re.match(r"^\s*(?:abstract|keywords?|introduction)\b", line, re.IGNORECASE)
            ),
            min(len(lines), start + 50),
        )
        candidates = []
        title_parts = {word for word in (title or "").casefold().split()}
        for index, line in enumerate(lines[start:stop], start):
            if (
                LABEL_PATTERN.match(line) or NON_TITLE_PATTERN.search(line)
                or AFFILIATION_WORD_PATTERN.search(line) or len(line.split()) > 12
                or CONFERENCE_MASTHEAD_PATTERN.match(line)
                or any(line.casefold().strip() == part for part in title_parts)
            ):
                continue
            name_candidate = re.sub(r"(?:\^?\d{1,2}|[¹²³⁴⁵⁶⁷⁸⁹⁰]+)", "", line).strip(" ,;*†")
            name_parts = _split_author_line(name_candidate)
            part_tokens = [part.replace("-", " ").split() for part in name_parts]
            all_parts_are_names = bool(part_tokens) and all(
                2 <= len(tokens) <= 5
                and all(re.fullmatch(r"(?:[A-Z][A-Za-z'’.-]*|[A-Z])", token) for token in tokens)
                for tokens in part_tokens
            )
            has_affiliation_marker = bool(re.search(r"\d{1,2}|[¹²³⁴⁵⁶⁷⁸⁹⁰]", line))
            is_multiple_author_line = bool(re.search(r"\b(?:and|&)\b|·", line, re.IGNORECASE))
            if all_parts_are_names and (has_affiliation_marker or is_multiple_author_line):
                candidates.extend((index, part) for part in name_parts)
                continue
            tokens = name_candidate.replace("-", " ").split()
            if (
                2 <= len(tokens) <= 5
                and ":" not in line and "@" not in line and "_" not in line
                and not AFFILIATION_WORD_PATTERN.search(line)
                and any(
                    AFFILIATION_WORD_PATTERN.search(following_line)
                    for following_line in lines[index + 1 : index + 8]
                )
                and all(re.fullmatch(r"(?:[A-Z][A-Za-z'’.-]*|[A-Z])", token) for token in tokens)
            ):
                candidates.append((index, line))
        if not candidates:
            return [], None, 0.0
        author_index = candidates[0][0]
        candidate_indices = [index for index, _ in candidates]
        author_text = "; ".join(value for _, value in candidates)
    else:
        candidate_indices = [author_index or 0]

    affiliation_lines = [
        line for line in lines[(author_index or 0) + 1 : 40]
        if AFFILIATION_WORD_PATTERN.search(line) and not TITLE_STOP_PATTERN.match(line)
    ]

    authors = []
    author_values = _split_author_line(author_text)
    for author_number, value in enumerate(author_values):
        markers = re.findall(r"(?:\^?(\d{1,2})|([¹²³⁴⁵⁶⁷⁸⁹⁰]+))", value)
        marker_keys = []
        for numeric, superscript in markers:
            marker_keys.extend(
                [numeric] if numeric else [SUPERSCRIPT_DIGITS[char] for char in superscript]
            )
        name = re.sub(r"(?:\^?\d{1,2}|[¹²³⁴⁵⁶⁷⁸⁹⁰]+)", "", value).strip(" ,;*†")
        if len(name.split()) < 2 or AFFILIATION_WORD_PATTERN.search(name):
            continue
        matched = [affiliations[key][0] for key in marker_keys if key in affiliations]
        if not matched and author_number < len(candidate_indices):
            source_index = candidate_indices[author_number]
            next_index = candidate_indices[author_number + 1] if author_number + 1 < len(candidate_indices) else min(source_index + 9, len(lines))
            nearby = lines[source_index + 1 : next_index]
            matched = [
                line for line in nearby
                if AFFILIATION_WORD_PATTERN.search(line)
                or re.search(r"\b[\w.-]+,\s*[\w.-]+(?:,\s*[\w.-]+)?\b", line)
            ]
            if not matched and len(affiliation_lines) == 1:
                matched = affiliation_lines
        affiliation = "; ".join(dict.fromkeys(matched)) or None
        department = None
        institution = None
        location = None
        if affiliation:
            department_match = re.search(
                r"((?:Dept\.?|Department|Faculty|School|Division|Laboratory|Centre|Center)\b[^,;]*)",
                affiliation,
                re.IGNORECASE,
            )
            department = department_match.group(1).strip() if department_match else None
            institution_match = re.search(
                r"((?:[\w&.'-]+\s+){0,5}(?:University|Institute|College|Academy|Hospital|Laboratory|Centre|Center)\b[^,;]*)",
                affiliation,
                re.IGNORECASE,
            )
            institution = institution_match.group(1).strip() if institution_match else None
            parts = [part.strip() for part in re.split(r"[,;]", affiliation) if part.strip()]
            location_pattern = re.compile(
                r"^[A-Z][A-Za-z.-]*(?:\s+[A-Z][A-Za-z.-]*){0,3}$"
            )
            location = parts[-1] if len(parts) > 1 and location_pattern.fullmatch(parts[-1]) else None
        authors.append(
            {
                "name": name,
                "department": department,
                "institution": institution,
                "location": location,
            }
        )
    evidence_text = "; ".join(lines[index] for index in candidate_indices if index < len(lines))
    return authors, evidence_text, 0.88 if authors else 0.0


def _layout_authors(document: str | Mapping, affiliation_context: list[str]) -> tuple[list[dict], str | None]:
    if not isinstance(document, Mapping):
        return [], None
    pages = document.get("cleaned_layout_blocks") or document.get("layout_blocks_by_page") or []
    if not pages or not pages[0]:
        return [], None

    blocks = pages[0]
    page_lines = _page_lines(document)[0]
    title, _, _ = _title(page_lines)
    title_tokens = set(re.findall(r"[a-z]+", (title or "").casefold()))
    title_y = min(
        (
            float(block.get("y0", 0)) for block in blocks
            if title and len(set(re.findall(r"[a-z]+", str(block.get("text", "")).casefold())) & title_tokens) >= 2
        ),
        default=0.0,
    )
    abstract_y = min(
        (
            float(block.get("y0", 0)) for block in blocks
            if re.search(r"^\s*abstract\b", str(block.get("text", "")), re.IGNORECASE | re.MULTILINE)
        ),
        default=float("inf"),
    )
    candidates = []
    for block_index, block in enumerate(blocks):
        block_text = str(block.get("text") or "")
        block_y = float(block.get("y0", 0))
        if block_y < title_y or block_y >= abstract_y:
            continue
        for line in block_text.splitlines():
            line = line.strip()
            if (
                not line or "@" in line or AFFILIATION_WORD_PATTERN.search(line)
                or re.fullmatch(r"[A-Z][\w .'-]+,\s*[A-Z][\w .'-]+", line)
                or CONFERENCE_MASTHEAD_PATTERN.match(line)
                or NON_TITLE_PATTERN.search(line)
            ):
                continue
            words = set(re.findall(r"[a-z]+", line.casefold()))
            if title_tokens and len(words & title_tokens) / max(1, len(words)) >= 0.5:
                continue
            names = _split_author_line(line)
            parsed_names = []
            for value in names:
                name = re.sub(r"(?:\^?\d{1,2}|[¹²³⁴⁵⁶⁷⁸⁹⁰]+)", "", value).strip(" ,;*†")
                tokens = name.replace("-", " ").split()
                if (
                    2 <= len(tokens) <= 5
                    and all(re.fullmatch(r"(?:[A-Z][A-Za-z'’.-]*|[A-Z])", token) for token in tokens)
                ):
                    parsed_names.append(value)
            has_marker = bool(AUTHOR_MARKER_LINE_PATTERN.search(line))
            if parsed_names and (has_marker or len(parsed_names) > 1 or block_y > 50):
                candidates.extend(
                    {
                        "block_index": block_index,
                        "x0": float(block.get("x0", 0)),
                        "y0": float(block.get("y0", 0)),
                        "name": name,
                    }
                    for name in parsed_names
                )

    if not candidates:
        return [], None
    candidates.sort(key=lambda item: (round(item["y0"] / 35), item["x0"]))
    marker_affiliations = _affiliation_entries(affiliation_context)
    for page_blocks in pages:
        for block in page_blocks:
            block_lines = [line.strip() for line in str(block.get("text", "")).splitlines() if line.strip()]
            for line_index, line in enumerate(block_lines[:-1]):
                marker = re.fullmatch(r"(\d{1,2})", line)
                if marker and re.search(r"\b(dept\.?|department|faculty|school|division)\b", block_lines[line_index + 1], re.IGNORECASE):
                    affiliation_lines = [block_lines[line_index + 1]]
                    for following in block_lines[line_index + 2 : line_index + 6]:
                        if (
                            re.search(r"\b(university|institute|college|academy|hospital|centre|center)\b", following, re.IGNORECASE)
                            or re.match(r"^(?:of|and)\b", following, re.IGNORECASE)
                            or re.fullmatch(r"[A-Z][A-Za-z.-]*(?:\s+[A-Z][A-Za-z.-]*){0,3},\s*[A-Z][A-Za-z.-]*(?:\s+[A-Z][A-Za-z.-]*){0,3}", following)
                        ):
                            affiliation_lines.append(following)
                    marker_affiliations[marker.group(1)] = (" ".join(affiliation_lines), line_index)
    shared_affiliations = []
    for index, line in enumerate(affiliation_context):
        if not re.match(r"^\s*(?:dept\.?|department|faculty|division|school\s+of)\b", line, re.IGNORECASE):
            continue
        affiliation_lines = [line]
        for following in affiliation_context[index + 1 : index + 6]:
            if (
                re.search(r"\b(university|institute|college|academy|hospital|centre|center)\b", following, re.IGNORECASE)
                or re.match(r"^\s*(?:of\b|and\b)", following, re.IGNORECASE)
                or re.fullmatch(r"[A-Z][A-Za-z.-]*(?:\s+[A-Z][A-Za-z.-]*){0,3},\s*[A-Z][A-Za-z.-]*(?:\s+[A-Z][A-Za-z.-]*){0,3}", following.strip())
            ):
                affiliation_lines.append(following)
            else:
                break
        shared_affiliations.append(" ".join(affiliation_lines))
    unique_shared_affiliations = list(dict.fromkeys(shared_affiliations))
    authors = []
    evidence_names = []
    for author_index, candidate in enumerate(candidates):
        marker_keys = []
        for numeric, superscript in re.findall(
            r"(?:\^?(\d{1,2})|([¹²³⁴⁵⁶⁷⁸⁹⁰]+))", candidate["name"]
        ):
            marker_keys.extend([numeric] if numeric else [SUPERSCRIPT_DIGITS[char] for char in superscript])
        affiliation_parts = [marker_affiliations[key][0] for key in marker_keys if key in marker_affiliations]
        if not affiliation_parts and marker_keys and len(unique_shared_affiliations) == 1:
            affiliation_parts = unique_shared_affiliations
        if not affiliation_parts:
            next_author_y = next(
                (
                    other["y0"] for other in candidates[author_index + 1 :]
                    if abs(other["x0"] - candidate["x0"]) < 55 and other["y0"] > candidate["y0"] + 5
                ),
                candidate["y0"] + 100,
            )
            nearby_blocks = [
                block for block in blocks
                if abs(float(block.get("x0", 0)) - candidate["x0"]) < 55
                and candidate["y0"] <= float(block.get("y0", 0)) < next_author_y
            ]
            affiliation_parts = []
            for block in nearby_blocks:
                block_lines = [line.strip() for line in str(block.get("text", "")).splitlines() if line.strip()]
                in_affiliation = False
                for line in block_lines:
                    if re.search(r"\b(?:copyright|exclusive licence|exclusive license|received|revised|accepted)\b", line, re.IGNORECASE):
                        in_affiliation = False
                        continue
                    if candidate["name"].casefold().replace(" ", "") in line.casefold().replace(" ", ""):
                        line = re.sub(re.escape(candidate["name"]), "", line, flags=re.IGNORECASE).strip()
                    if AFFILIATION_WORD_PATTERN.search(line):
                        in_affiliation = True
                    elif re.fullmatch(
                        r"[A-Z][A-Za-z.-]*(?:\s+[A-Z][A-Za-z.-]*){0,3},\s*[A-Z][A-Za-z.-]*(?:\s+[A-Z][A-Za-z.-]*){0,3}",
                        line,
                    ):
                        in_affiliation = True
                    elif in_affiliation and re.match(r"^(?:of|and)\b|^[A-Z][a-z]{1,12}$", line):
                        in_affiliation = True
                    elif "@" in line or re.search(r"\b(?:abstract|keywords?)\b", line, re.IGNORECASE):
                        in_affiliation = False
                    else:
                        in_affiliation = False
                    if in_affiliation and line:
                        affiliation_parts.append(line)
        affiliation = "\n".join(dict.fromkeys(affiliation_parts))
        department_match = re.search(
            r"^\s*((?:Dept\.?|Department|Faculty|School|Division|Laboratory|Centre|Center)\b[^,;\n]*)",
            affiliation,
            re.IGNORECASE | re.MULTILINE,
        )
        department = department_match.group(1).strip() if department_match else None
        institution_lines = [
            line.strip() for line in affiliation.splitlines()
            if re.search(r"\b(university|institute|college|academy|hospital|laboratory|centre|center)\b", line, re.IGNORECASE)
        ]
        for line_index, line in enumerate(affiliation.splitlines()[:-1]):
            if line.rstrip().casefold().endswith("and"):
                following = affiliation.splitlines()[line_index + 1].strip()
                if re.fullmatch(r"[A-Z][a-z]{1,15}", following):
                    institution_lines.append(f"{line.strip()} {following}")
        institution_matches = []
        for line in institution_lines:
            match = re.search(
                r"((?:[\w&.'-]+\s+){0,7}(?:University|Institute|College|Academy|Hospital|Laboratory|Centre|Center)(?:\s+(?:of|and|for)\s+[\w&.'-]+){0,7})",
                line,
                re.IGNORECASE,
            )
            if match:
                institution_matches.append(match.group(1).strip())
        institution = "; ".join(dict.fromkeys(institution_matches)) or None
        location = next(
            (
                line.strip() for line in affiliation.splitlines()
                if re.fullmatch(
                    r"[A-Z][A-Za-z.-]*(?:\s+[A-Z][A-Za-z.-]*){0,3},\s*(?:India|USA|United States|UK|United Kingdom|Canada|Australia|China|Japan)",
                    line.strip(),
                    re.IGNORECASE,
                )
            ),
            None,
        )
        authors.append(
            {
                "name": re.sub(r"(?:\^?\d{1,2}|[¹²³⁴⁵⁶⁷⁸⁹⁰]+)", "", candidate["name"]).strip(" ,;*†"),
                "department": department,
                "institution": institution,
                "location": location,
            }
        )
        evidence_names.append(candidate["name"])
    return authors, "; ".join(evidence_names)


def _unambiguous_shared_affiliation(lines: list[str]) -> tuple[str | None, str | None, str | None, str | None]:
    records = []
    for index, line in enumerate(lines):
        department_match = re.match(
            r"^\s*((?:Dept\.?|Department|Faculty|School|Division)\b[^,;]*)",
            line,
            re.IGNORECASE,
        )
        if not department_match:
            continue
        context = [line]
        for following in lines[index + 1 : index + 8]:
            if (
                "@" in following
                or re.search(r"\b(?:copyright|exclusive licence|exclusive license|received|revised|accepted|abstract|references)\b", following, re.IGNORECASE)
                or re.match(r"^\s*(?:Dept\.?|Department|Faculty|School|Division)\b", following, re.IGNORECASE)
            ):
                break
            if (
                re.search(r"\b(university|institute|college|academy|hospital|centre|center)\b", following, re.IGNORECASE)
                or re.match(r"^\s*(?:of\b|and\b)", following, re.IGNORECASE)
                or re.fullmatch(r"[A-Z][A-Za-z.-]*(?:\s+[A-Z][A-Za-z.-]*){0,3},\s*[A-Z][A-Za-z.-]*(?:\s+[A-Z][A-Za-z.-]*){0,3}(?:\s+\d{5,6})?,\s*[A-Z][A-Za-z.-]+", following.strip())
            ):
                context.append(following.strip())
            else:
                break

        organization_parts = []
        for value in context:
            organization_parts.extend(
                part.strip() for part in value.split(",")
                if re.search(r"\b(university|institute|college|academy|hospital|centre|center)\b", part, re.IGNORECASE)
                or re.match(r"^(?:of|and)\b", part.strip(), re.IGNORECASE)
            )
        joined_organization = " ".join(organization_parts)
        institution_match = re.search(
            r"((?:[A-Z][\w&.'-]*\s+){0,6}(?:University|Institute|College|Academy|Hospital|Centre|Center)(?:\s+(?:of|and|for)\s+[A-Z][\w&.'-]*){0,6})",
            joined_organization,
            re.IGNORECASE,
        )
        location = next(
            (
                value.strip() for value in context
                if re.fullmatch(r"[A-Z][A-Za-z.-]*(?:\s+[A-Z][A-Za-z.-]*){0,3},\s*[A-Z][A-Za-z.-]*(?:\s+[A-Z][A-Za-z.-]*){0,3}(?:\s+\d{5,6})?,\s*[A-Z][A-Za-z.-]+", value.strip())
            ),
            None,
        )
        records.append(
            (
                department_match.group(1).strip(),
                institution_match.group(1).strip() if institution_match else None,
                location,
                " ".join(context),
            )
        )

    if not records:
        return None, None, None, None
    unique_departments = list(dict.fromkeys(record[0] for record in records))
    unique_institutions = list(dict.fromkeys(record[1] for record in records if record[1]))
    unique_locations = list(dict.fromkeys(record[2] for record in records if record[2]))
    unique_evidence = list(dict.fromkeys(record[3] for record in records))
    byline = " ".join(lines[:35])
    repeated_markers = re.findall(r"\b[A-Z][A-Za-z.'-]*\d\b", byline)
    shared_affiliation = len(records) > 1 or len(repeated_markers) > 1
    return (
        unique_departments[0] if len(unique_departments) == 1 and shared_affiliation else None,
        unique_institutions[0] if len(unique_institutions) == 1 and shared_affiliation else None,
        unique_locations[0] if len(unique_locations) == 1 and shared_affiliation else None,
        "; ".join(unique_evidence) if unique_evidence else None,
    )


def _valid_issn(value: str) -> bool:
    digits = value.replace("-", "").upper()
    if not re.fullmatch(r"\d{7}[\dX]", digits):
        return False
    checksum = sum(int(digit) * weight for digit, weight in zip(digits[:7], range(8, 1, -1)))
    check_digit = (11 - checksum % 11) % 11
    return digits[-1] == ("X" if check_digit == 10 else str(check_digit))


def _issns(lines: list[str]) -> tuple[dict, str | None, list[str]]:
    result = {"print": None, "electronic": None}
    evidence = None
    warnings = []
    for line in lines[:55]:
        match = ISSN_LABEL_PATTERN.search(line)
        if not match or re.search(r"\bisbn\b", line, re.IGNORECASE):
            continue
        kind = "electronic" if re.search(r"electronic|online|e-?issn", match.group(1), re.IGNORECASE) else "print"
        values = ISSN_PATTERN.findall(match.group(2))
        value = next((f"{first}-{second.upper()}" for first, second in values if _valid_issn(f"{first}-{second}")), None)
        if value:
            result[kind] = value
            evidence = line
        elif values:
            warnings.append(f"An ISSN-like value could not pass checksum validation: {line[:120]}")
        else:
            warnings.append(f"An ISSN label was present but its value could not be parsed: {line[:120]}")
    return result, evidence, warnings


def _publication_date(lines: list[str]) -> tuple[dict, str | None, float, list[str]]:
    candidates = []
    warnings = []
    for index, line in enumerate(lines[:80]):
        if DATE_EXCLUSION_PATTERN.search(line):
            continue
        match = DATE_LABEL_PATTERN.search(line)
        if not match:
            continue
        date_text = match.group(2)
        year_match = YEAR_PATTERN.search(date_text)
        if not year_match:
            warnings.append(f"A publication-date label was present without a reliable year: {line[:120]}")
            continue
        month = next(
            (name for token, name in MONTHS.items() if re.search(rf"\b{token}\b", date_text, re.IGNORECASE)),
            None,
        )
        label = match.group(1).casefold()
        rank = 0 if "publication date" in label or label == "published" else 1 if "online" in label else 2
        candidates.append((rank, index, month, year_match.group(1), line))
    if not candidates:
        for index, line in enumerate(lines[:35]):
            if CONFERENCE_MASTHEAD_PATTERN.match(line):
                year_match = YEAR_PATTERN.search(line)
                if year_match:
                    candidates.append((4, index, None, year_match.group(1), line.split("|", 1)[0].strip()))
                    break
            if not re.search(r"\b(?:volume|vol\.)\s*\d+", line, re.IGNORECASE):
                continue
            year_match = YEAR_PATTERN.search(line)
            if not year_match:
                continue
            month = next(
                (name for token, name in MONTHS.items() if re.search(rf"\b{token}\b", line, re.IGNORECASE)),
                None,
            )
            candidates.append((3, index, month, year_match.group(1), line))
    if not candidates:
        return {"month": None, "year": None}, None, 0.0, warnings
    years = {candidate[3] for candidate in candidates}
    if len(years) > 1:
        chosen_year = min(candidates)[3]
        warnings.append(
            f"Conflicting publication years were found ({', '.join(sorted(years))}); the most explicit publication label supports {chosen_year}."
        )
    rank, _, month, year, evidence = min(candidates)
    return {"month": month, "year": year}, evidence, 0.96 if month else 0.90, warnings


def _journal_and_conference(lines: list[str]) -> tuple[str | None, str | None, str | None, int | None, float]:
    journal, journal_index = _field(lines[:65], ("journal", "journal name", "container title"))
    conference, conference_index = _field(lines[:65], ("conference", "conference name", "proceedings"))
    container_confidence = 0.95 if journal or conference else 0.0
    if conference is None:
        conference_line = next(
            ((index, line) for index, line in enumerate(lines[:20])
             if not line.lstrip().startswith(("•", "-", "*"))
             and CONFERENCE_MASTHEAD_PATTERN.match(line)),
            None,
        )
        if conference_line:
            conference_index, conference = conference_line
            conference = conference.split("|", 1)[0].strip()
            conference = re.sub(r"\s+\d{1,4}$", "", conference)
            container_confidence = 0.84
    if journal is None and conference is None:
        for index, line in enumerate(lines[:20]):
            match = re.match(r"^(.{5,120}?),\s*(?:volume|vol\.)\s*\d+\b", line, re.IGNORECASE)
            if match:
                journal, journal_index = match.group(1).strip(" ,"), index
                container_confidence = 0.84
                break
    if journal is None and conference is None:
        article_type_index = next(
            (index for index, line in enumerate(lines[:20]) if ARTICLE_TYPE_PATTERN.match(line)),
            None,
        )
        if article_type_index is not None:
            masthead = next(
                (
                    (index, line) for index, line in enumerate(lines[:article_type_index])
                    if line and not DOI_PATTERN.search(line)
                    and not line.lower().startswith(("http://", "https://"))
                ),
                None,
            )
            if masthead:
                journal_index, journal = masthead
                container_confidence = 0.90
    if journal and conference:
        return journal, conference, "unknown", journal_index, container_confidence
    if conference:
        return None, conference, "conference", conference_index, container_confidence
    if journal:
        return journal, None, "journal", journal_index, container_confidence
    return None, None, None, None, 0.0


def _doi(lines: list[str], metadata: dict | None = None) -> tuple[str | None, str | None, float, list[str], str | None]:
    explicit = []
    candidates = []
    warnings = []
    metadata_end = next(
        (
            index for index, line in enumerate(lines[:100])
            if re.match(r"^\s*(?:abstract|keywords?|introduction)\b", line, re.IGNORECASE)
        ),
        min(len(lines), 40),
    )
    for index, line in enumerate(lines[:100]):
        match = re.search(
            r"(?:\bdoi\s*:?\s*|(?:https?://)?(?:dx\.)?doi\.org/)(10\.\d{4,9}/[-._;()/:A-Z0-9]+)",
            line,
            re.IGNORECASE,
        )
        if match:
            explicit.append((normalize_doi(match.group(1)), line, index))
        else:
            if re.search(r"\bdoi\b", line, re.IGNORECASE):
                warnings.append(f"A DOI label was present but its value could not be parsed reliably: {line[:120]}")
            for doi_match in DOI_PATTERN.finditer(line):
                candidates.append((normalize_doi(doi_match.group(0)), line, index))
    options = explicit or candidates
    distinct = list(dict.fromkeys(value for value, _, _ in options if value))
    if len(distinct) > 1:
        metadata = metadata or {}
        if metadata.get("title"):
            from app.services.doi_verifier import verify_doi

            verified = [
                (value, verify_doi(value, metadata))
                for value in distinct
            ]
            matches = [(value, result) for value, result in verified if result.get("verified")]
            if len(matches) == 1:
                value, result = matches[0]
                source_line = next(line for candidate, line, _ in options if candidate == value)
                warnings.append(f"Crossref uniquely matched DOI {value} to the current paper's title/authors.")
                return value, source_line, max(0.80, float(result.get("confidence") or 0.0)), warnings, "Crossref"
        warnings.append("Multiple current-article DOI candidates were found outside References; DOI was left unset because ownership is ambiguous.")
        return None, None, 0.0, warnings, None
    if not distinct:
        return None, None, 0.0, warnings, None
    value = distinct[0]
    source, source_index = next((line, index) for candidate, line, index in options if candidate == value)
    if explicit and source_index < metadata_end:
        return value, source, 0.96, warnings, None

    metadata = metadata or {}
    if metadata.get("title"):
        from app.services.doi_verifier import verify_doi

        verification = verify_doi(value, metadata)
        if verification.get("verified"):
            warnings.append(f"Crossref matched DOI {value} to the current paper's title/authors.")
            return value, source, max(0.80, float(verification.get("confidence") or 0.0)), warnings, "Crossref"
    warnings.append("A DOI candidate was found outside the article metadata block but could not be verified against the current paper.")
    return None, None, 0.0, warnings, None


def _extract_metadata_locally(document: str | Mapping) -> dict:
    """Extract validated paper metadata from page-aware text and local document context."""
    pages = _page_lines(document)
    all_lines = [line for page in pages for line in page]
    first_page = pages[0] if pages else []
    early_lines = first_page or all_lines[:80]
    warnings = ["Local structural extraction is active; no metadata-generating LLM provider is configured."]

    title, title_index, title_confidence = _title(early_lines)
    authors, author_evidence, author_confidence = _extract_authors(
        early_lines,
        title_index=title_index,
        title=title,
        affiliation_context=all_lines,
    )
    layout_authors, layout_author_evidence = _layout_authors(document, all_lines)
    if layout_authors:
        authors = layout_authors
        author_evidence = layout_author_evidence
        author_confidence = 0.94
    shared_department, shared_institution, shared_location, shared_affiliation_evidence = (
        _unambiguous_shared_affiliation(all_lines)
    )
    if authors:
        for author in authors:
            if shared_department:
                author["department"] = shared_department
            if shared_institution:
                author["institution"] = shared_institution
            if shared_location:
                author["location"] = shared_location
    journal, conference, document_type, container_index, container_confidence = _journal_and_conference(all_lines)
    publication_date, date_evidence, date_confidence, date_warnings = _publication_date(all_lines)
    issn, issn_evidence, issn_warnings = _issns(all_lines)
    doi, doi_evidence, doi_confidence, doi_warnings, doi_source = _doi(
        all_lines,
        {
            "title": title,
            "authors": authors,
            "publication_year": publication_date.get("year"),
            "journal": journal,
            "conference": conference,
        },
    )
    warnings.extend(date_warnings + issn_warnings + doi_warnings)

    if document_type is None:
        document_type = "unknown"
    if document_type == "conference":
        journal = None
        ugc_status = "not_applicable"
    elif document_type == "journal":
        ugc_status = "not_verified"
        warnings.append("UGC CARE status was not verified because no authoritative UGC CARE source is configured.")
    else:
        ugc_status = "unknown"

    department_evidence = shared_affiliation_evidence
    if department_evidence is None:
        department_evidence = next(
            (
                line for line in all_lines
                if re.match(r"\s*(?:dept\.?|department|faculty|school|division)\b", line, re.IGNORECASE)
            ),
            None,
        )
    journal_evidence = all_lines[container_index] if container_index is not None else None
    evidence = {
        "paper_title": _evidence(title, 1 if title_index is not None else None),
        "authors": _evidence(author_evidence, 1),
        "departments": _evidence(department_evidence, _evidence_page(pages, department_evidence)),
        "journal_name": _evidence(journal_evidence, _evidence_page(pages, journal_evidence)),
        "publication_date": _evidence(date_evidence, _evidence_page(pages, date_evidence)),
        "issn": _evidence(issn_evidence, _evidence_page(pages, issn_evidence)),
        "ugc_care": None,
        "doi": _evidence(doi_evidence, _evidence_page(pages, doi_evidence)),
    }
    if evidence["doi"] and doi_source:
        evidence["doi"]["source"] = doi_source
    department_confidence = 0.85 if any(author.get("department") for author in authors) else 0.0
    confidence = {
        "paper_title": title_confidence,
        "authors": author_confidence,
        "departments": department_confidence,
        "journal_name": container_confidence if journal else 0.0,
        "publication_date": date_confidence,
        "issn": 0.96 if any(issn.values()) else 0.0,
        "ugc_care": 0.0,
        "doi": doi_confidence,
    }
    missing_fields = []
    if not title:
        missing_fields.append("paper_title")
    if not authors:
        missing_fields.append("authors")
    if authors and any(author["department"] is None for author in authors):
        missing_fields.append("author_departments")
    if document_type == "journal" and not journal:
        missing_fields.append("journal_name")
    if not publication_date["year"]:
        missing_fields.append("publication_date")
    if not any(issn.values()):
        missing_fields.append("issn")
    if ugc_status == "not_verified":
        missing_fields.append("ugc_care.link")
    if not doi:
        missing_fields.append("doi")
    normalized = ResearchPaperMetadata(
        paper_title=title,
        authors=authors,
        journal_name=journal,
        publication_date=publication_date,
        issn=issn,
        ugc_care={"status": ugc_status, "link": None},
        doi=doi,
        document_type=document_type,
        conference_name=conference,
        confidence=confidence,
        evidence=evidence,
        warnings=warnings,
        missing_fields=missing_fields,
    )
    return normalized.model_dump(mode="json")


def _crossref_affiliation_fields(value: str) -> dict:
    department_match = re.search(
        r"((?:Dept\.?|Department|Faculty|School|Division)\b[^,;]*)",
        value,
        re.IGNORECASE,
    )
    institution_match = re.search(
        r"((?:[\w&.'-]+\s+){0,8}(?:University|Institute|College|Academy|Hospital|Centre|Center)(?:\s+(?:of|and|for)\s+[\w&.'-]+){0,8})",
        value,
        re.IGNORECASE,
    )
    parts = [part.strip() for part in value.split(",") if part.strip()]
    country_names = {"india", "usa", "united states", "uk", "united kingdom", "canada", "australia", "china", "japan"}
    location = f"{parts[-2]}, {parts[-1]}" if len(parts) > 1 and parts[-1].casefold() in country_names else None
    return {
        "department": department_match.group(1).strip() if department_match else None,
        "institution": institution_match.group(1).strip() if institution_match else None,
        "location": location,
    }


def _enrich_from_crossref(metadata: dict) -> dict:
    from app.core.config import settings
    from app.services.doi_verifier import verify_doi

    if (
        not settings.crossref_metadata_verification
        or not metadata.get("doi")
        or not metadata.get("paper_title")
        or not metadata.get("evidence", {}).get("doi")
        or metadata["evidence"]["doi"].get("page") != 1
    ):
        return metadata

    verification = verify_doi(metadata["doi"], {"title": metadata["paper_title"], "authors": []})
    title_similarity = verification.get("title_similarity") or 0.0
    crossref_authors = verification.get("crossref_authors") or []
    local_last_names = {
        re.findall(r"[a-z0-9]+", author.get("name", "").casefold())[-1]
        for author in metadata.get("authors", [])
        if re.findall(r"[a-z0-9]+", author.get("name", "").casefold())
    }
    crossref_last_names = {
        re.findall(r"[a-z0-9]+", author.get("name", "").casefold())[-1]
        for author in crossref_authors
        if re.findall(r"[a-z0-9]+", author.get("name", "").casefold())
    }
    author_overlap = (
        len(local_last_names & crossref_last_names) / max(1, len(crossref_last_names))
        if crossref_last_names
        else 0.0
    )
    doi_evidence_text = metadata["evidence"]["doi"]["text"]
    doi_in_publisher_header = (
        metadata["evidence"]["doi"].get("page") == 1
        and normalize_doi(metadata["doi"]).casefold() in normalize_doi(doi_evidence_text).casefold()
        and bool(re.search(r"doi|ieee|springer", doi_evidence_text, re.IGNORECASE))
    )
    strong_publisher_match = (
        doi_in_publisher_header
        and title_similarity >= 0.55
        and author_overlap >= 0.5
    )
    if not verification.get("verified") and not strong_publisher_match:
        return metadata
    if verification.get("verified") and title_similarity < 0.95 and not strong_publisher_match:
        return metadata

    result = ResearchPaperMetadata.model_validate(metadata).model_dump(mode="json")
    warnings = list(result["warnings"])
    crossref_title = verification.get("crossref_title")
    if crossref_title and strong_publisher_match and _normalized_metadata_text(crossref_title) != _normalized_metadata_text(result["paper_title"]):
        warnings.append(
            f"The PDF title block was incomplete; Crossref supplied the complete title after page-one DOI and author confirmation: {crossref_title}."
        )
        result["paper_title"] = crossref_title
        result["confidence"]["paper_title"] = 0.97
        result["evidence"]["paper_title"] = {
            "text": crossref_title,
            "page": 1,
            "source": "Crossref title matched to page-one DOI and authors",
        }

    crossref_type = verification.get("crossref_type")
    crossref_container = verification.get("crossref_container")
    if crossref_type == "journal-article":
        result["document_type"] = "journal"
        result["conference_name"] = None
        if crossref_container:
            result["journal_name"] = crossref_container
            result["confidence"]["journal_name"] = max(result["confidence"]["journal_name"], 0.96)
            result["evidence"]["journal_name"] = {
                "text": f"Crossref container title: {crossref_container}",
                "page": None,
                "source": "Crossref",
            }
    elif crossref_type == "proceedings-article":
        result["document_type"] = "conference"
        result["journal_name"] = None
        if crossref_container:
            result["conference_name"] = crossref_container

    crossref_year = verification.get("crossref_year")
    crossref_month = verification.get("crossref_month")
    month_name = (
        next((month for month in MONTHS.values() if list(MONTHS.values()).index(month) + 1 == crossref_month), None)
        if crossref_month
        else None
    )
    if crossref_year:
        current_year = result["publication_date"]["year"]
        if current_year and current_year != str(crossref_year):
            warnings.append(
                f"The PDF lists publication year {current_year}, while the DOI-matched Crossref record lists {crossref_year}; Crossref was selected."
            )
        result["publication_date"] = {"month": month_name, "year": str(crossref_year)}
        result["confidence"]["publication_date"] = 0.96 if month_name else 0.90
        result["evidence"]["publication_date"] = {
            "text": f"Crossref publication date: {month_name + ' ' if month_name else ''}{crossref_year}",
            "page": None,
            "source": "Crossref",
        }

    crossref_authors = verification.get("crossref_authors") or []
    if crossref_authors:
        existing = {
            re.sub(r"[^a-z0-9]", "", author.get("name", "").casefold()): author
            for author in result["authors"]
        }
        authors = []
        crossref_affiliation_evidence = []
        for crossref_author in crossref_authors:
            name = crossref_author.get("name")
            if not name:
                continue
            key = re.sub(r"[^a-z0-9]", "", name.casefold())
            previous = existing.get(key, {})
            affiliation = "; ".join(crossref_author.get("affiliations", []))
            if affiliation:
                crossref_affiliation_evidence.append(f"{name}: {affiliation}")
            parsed_affiliation = _crossref_affiliation_fields(affiliation) if affiliation else {}
            author_evidence_text = result.get("evidence", {}).get("authors") or {}
            has_shared_pdf_affiliation = bool(
                result.get("evidence", {}).get("departments")
                and previous.get("department")
                and len(re.findall(r"\b[A-Z][A-Za-z.'-]*\d\b", author_evidence_text.get("text", ""))) >= 2
            )
            authors.append(
                {
                    "name": name,
                    "department": parsed_affiliation.get("department") or (previous.get("department") if has_shared_pdf_affiliation else None),
                    "institution": parsed_affiliation.get("institution") or (previous.get("institution") if has_shared_pdf_affiliation else None),
                    "location": parsed_affiliation.get("location") or (previous.get("location") if has_shared_pdf_affiliation else None),
                }
            )
        if authors:
            result["authors"] = authors
            result["confidence"]["authors"] = 0.98
            result["evidence"]["authors"] = {
                "text": "; ".join(author["name"] for author in authors),
                "page": None,
                "source": "Crossref",
            }
            if any(author.get("department") for author in authors):
                result["confidence"]["departments"] = 0.96
                result["evidence"]["departments"] = {
                    "text": "; ".join(crossref_affiliation_evidence),
                    "page": None,
                    "source": "Crossref",
                }
            elif not any(author.get("department") for author in authors):
                result["confidence"]["departments"] = 0.0
                if not any(author.get("department") for author in metadata.get("authors", [])):
                    result["evidence"]["departments"] = None

    crossref_issn = verification.get("crossref_issn") or []
    issn_formats = verification.get("crossref_issn_formats") or {}
    if crossref_issn:
        verified_issns = {
            issn_formats[value]: value
            for value in crossref_issn
            if issn_formats.get(value) in {"print", "electronic"}
        }
        if verified_issns:
            result["issn"] = {
                "print": verified_issns.get("print"),
                "electronic": verified_issns.get("electronic"),
            }
            result["confidence"]["issn"] = 0.98
            result["evidence"]["issn"] = {
                "text": "; ".join(f"{kind} ISSN: {value}" for kind, value in verified_issns.items()),
                "page": None,
                "source": "Crossref + ISSN International Centre",
            }
        else:
            warnings.append("Crossref lists ISSNs for this journal, but their print/electronic media could not be verified.")

    if result["document_type"] == "conference":
        result["ugc_care"] = {"status": "not_applicable", "link": None}
    else:
        result["ugc_care"] = {"status": "not_verified", "link": None}
        if not any("UGC CARE" in warning for warning in warnings):
            warnings.append("UGC CARE status was not verified because no authoritative UGC CARE source is configured.")
    result["evidence"]["doi"] = {
        "text": result["doi"],
        "page": result["evidence"]["doi"].get("page"),
        "source": "PDF + Crossref",
    }
    if result["evidence"].get("paper_title"):
        result["evidence"]["paper_title"]["source"] = "PDF + Crossref"
    result["confidence"]["doi"] = 0.98
    warnings.append("DOI metadata was verified against Crossref using title similarity.")
    result["warnings"] = list(dict.fromkeys(warnings))
    return ResearchPaperMetadata.model_validate(result).model_dump(mode="json")


def _normalized_metadata_text(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").casefold())


def extract_metadata(document: str | Mapping) -> dict:
    """Run local structural extraction, then validate optional Ollama enrichment."""
    fallback = _enrich_from_crossref(_extract_metadata_locally(document))
    from app.services.semantic_metadata import extract_with_ollama

    return extract_with_ollama(document, fallback)
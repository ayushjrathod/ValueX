import re

from src.agents.catalog import AgentName
from src.agents.contracts import AgentRequest, AgentResponse

_DISCLAIMER = (
    "General information only, not personalized investment advice. "
    "For decisions involving your money, consider your goals, risk tolerance, and time horizon."
)

_GREETING_HINT = (
    "I can explain investing basics, review a portfolio, discuss a ticker, or help you frame a planning question."
)

_TOPIC_GUIDES: dict[str, str] = {
    "mutual fund": (
        "A mutual fund pools money from many investors and buys a basket of assets. "
        "You own shares of the fund rather than each underlying holding, and the fund is usually priced once per trading day."
    ),
    "compound interest": (
        "Compound interest means your returns start earning returns of their own. "
        "Over long periods, that snowball effect can matter more than any single contribution."
    ),
    "p/e ratio": (
        "The P/E ratio compares a company's share price with its earnings per share. "
        "A higher P/E can reflect stronger growth expectations, but it can also mean the stock is expensive relative to current profits."
    ),
    "etf": (
        "An ETF is a fund that trades on an exchange like a stock. "
        "Many ETFs track an index, sector, or theme and can be bought or sold throughout the trading day."
    ),
    "index fund": (
        "An index fund aims to match the performance of a market index such as the S&P 500 instead of trying to beat it. "
        "It can be structured either as a mutual fund or as an ETF."
    ),
}

_COMMON_SHORT_QUERIES = {
    "hi",
    "hello",
    "hey",
    "thanks",
    "thank you",
    "bye",
}


def run(request: AgentRequest) -> AgentResponse:
    query = (request.query or "").strip()
    topics = _normalized_topics(request.entities.get("topics"))

    if _is_thanks(query):
        message = (
            "You're welcome. "
            f"{_GREETING_HINT} Ask about a term, a ticker, or your own portfolio when you're ready."
        )
    elif _is_greeting(query):
        message = f"Hello. {_GREETING_HINT}"
    elif _looks_like_gibberish(query, topics):
        message = (
            "I couldn't map that to a clear finance question. "
            "Try rephrasing with a topic, ticker, or goal, for example: 'what is an ETF?', 'how is AAPL doing?', or 'review my portfolio'."
        )
    else:
        message = _build_educational_response(query, topics)

    return AgentResponse(
        status="ok",
        intent=request.intent,
        agent=AgentName.GENERAL_QUERY,
        entities=request.entities,
        message=message,
        disclaimer=_DISCLAIMER,
    )


def _build_educational_response(query: str, topics: list[str]) -> str:
    if _is_etf_vs_index_fund(query, topics):
        return (
            "An index fund describes the investment approach: it tracks an index rather than trying to beat it. "
            "An ETF describes the wrapper: it trades on an exchange during the day like a stock. "
            "So an index fund can be an ETF, but it can also be a mutual fund."
        )

    if topics:
        primary_topic = topics[0]
        guide = _TOPIC_GUIDES.get(primary_topic)
        if guide:
            if len(topics) == 1:
                return guide
            remainder = ", ".join(topics[1:])
            return f"{guide} If you want, I can also break down {remainder} in the same plain-English way."

        joined_topics = ", ".join(topics)
        return (
            f"I can help with {joined_topics}. "
            "Ask a more specific follow-up such as what it means, when it is useful, what risks it carries, or how it differs from an alternative."
        )

    if query:
        return (
            "I can help explain finance concepts in plain language, but this question is still broad. "
            "If you tighten it to one concept, ticker, or goal, I can answer more directly."
        )

    return (
        "I can explain investing basics, but I need a question to work from. "
        "Try a concept like 'compound interest', a ticker like 'AAPL', or a request like 'review my portfolio'."
    )


def _normalized_topics(raw_topics: object) -> list[str]:
    if not isinstance(raw_topics, list):
        return []
    normalized: list[str] = []
    for topic in raw_topics:
        if isinstance(topic, str) and topic.strip():
            normalized.append(topic.strip().lower())
    return normalized


def _is_greeting(query: str) -> bool:
    lowered = query.lower().strip()
    return lowered in {"hi", "hello", "hey", "hello there", "hi there"}


def _is_thanks(query: str) -> bool:
    lowered = query.lower().strip()
    return lowered in {"thanks", "thank you", "thx", "cheers"}


def _looks_like_gibberish(query: str, topics: list[str]) -> bool:
    lowered = query.lower().strip()
    if not lowered or topics or lowered in _COMMON_SHORT_QUERIES:
        return False

    words = re.findall(r"[a-zA-Z]+", lowered)
    if len(words) != 1:
        return False

    word = words[0]
    return len(word) >= 5 and len(set(word)) >= 5


def _is_etf_vs_index_fund(query: str, topics: list[str]) -> bool:
    lowered = query.lower()
    topic_set = set(topics)
    return (
        {"etf", "index fund"}.issubset(topic_set)
        or ("difference" in lowered and "etf" in lowered and "index fund" in lowered)
    )

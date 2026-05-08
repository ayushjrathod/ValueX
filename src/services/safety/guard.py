import pickle
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from src.config.settings import get_settings


class SafetyVerdict(BaseModel):
    model_config = ConfigDict(frozen=True)

    blocked: bool
    category: str | None = None
    message: str | None = None


_MESSAGES: dict[str, str] = {
    "insider_trading": "I cannot help with trading on material non-public information. I can explain the rules around insider trading or suggest compliant next steps.",
    "market_manipulation": "I cannot help design or coordinate market manipulation. I can explain why these practices are illegal and how markets are monitored.",
    "money_laundering": "I cannot help hide funds, avoid reporting requirements, or obscure proceeds. I can explain AML obligations and compliant record-keeping at a high level.",
    "guaranteed_returns": "I cannot promise guaranteed investment returns or identify certain winners. I can help compare risks, historical ranges, and realistic scenarios.",
    "reckless_advice": "I cannot encourage an unsuitable all-in, leveraged, or financially reckless trade. I can help discuss risk controls and more balanced alternatives.",
    "sanctions_evasion": "I cannot help bypass sanctions or hide sanctioned transactions. I can explain sanctions screening and compliance obligations.",
    "fraud": "I cannot help create fake documents or misrepresent financial activity. I can help explain legitimate documentation and compliance expectations.",
}

# Keyword sets used only to assign the correct category after the model blocks.
_CATEGORY_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("insider_trading", ("insider", "non-public", "confidential", "tip", "leaked", "announcement", "earnings")),
    ("market_manipulation", ("pump", "spoof", "wash trade", "manipulat", "inflate", "coordinated")),
    ("money_laundering", ("launder", "reporting", "shell company", "obscure", "dirty money", "illegal funds", "tax authorit", "structur")),
    ("guaranteed_returns", ("guarantee", "promise", "certain", "foolproof", "risk free", "double")),
    ("reckless_advice", ("retirement savings", "emergency fund", "pension", "mortgage", "margin loan", "leveraged", "everything i own", "college fund", "high risk")),
    ("sanctions_evasion", ("sanction", "ofac", "bypass")),
    ("fraud", ("fake", "forge", "fabricat", "claim losses")),
)

_MODEL_PATH = Path(__file__).parent / "safety_classifier.pkl"
_model = None


def _load_model():
    global _model
    if _model is None:
        with open(_MODEL_PATH, "rb") as f:
            _model = pickle.load(f)
    return _model


def warm_load() -> None:
    _load_model()


def check(query: str) -> SafetyVerdict:
    model = _load_model()
    proba = model.predict_proba([query])[0]
    # Higher threshold reduces false positives on legitimate financial queries
    # that share vocabulary with harmful ones (e.g. "returns", "fund", "trade").
    blocked = bool(proba[1] >= get_settings().safety_block_threshold)

    if not blocked:
        return SafetyVerdict(blocked=False)

    category = _classify_category(query.lower())
    return SafetyVerdict(
        blocked=True,
        category=category,
        message=_MESSAGES.get(category, _MESSAGES["fraud"]),
    )


def _classify_category(q: str) -> str:
    for category, keywords in _CATEGORY_KEYWORDS:
        if any(kw in q for kw in keywords):
            return category
    return "fraud"

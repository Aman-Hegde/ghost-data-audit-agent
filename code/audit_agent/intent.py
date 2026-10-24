"""Conservative intent classification with an explicit adjudication seam."""

from __future__ import annotations

import re
import unicodedata
from typing import Protocol

from .models import IntentDecision, IntentKind


class IntentAdjudicator(Protocol):
    def adjudicate(self, text: str) -> IntentDecision: ...


def _normalized_text(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


class MultilingualRuleAdjudicator:
    """High-precision multilingual rules; unknown language remains ambiguous."""

    _delete_patterns = (
        r"\b(eliminar|eliminación|borrar)\b.*\b(cuenta|datos)\b",
        r"\b(suppression|supprimer|effacer)\b.*\b(compte|données)\b",
        r"\b(exclusão|excluir|apagar)\b.*\b(conta|dados)\b",
        r"\b(löschen|löschung)\b.*\b(konto|daten)\b",
        r"(?:アカウント|個人情報).*(?:削除|消去)",
        r"(?:계정|개인정보).*(?:삭제|영구 삭제)",
    )

    def adjudicate(self, text: str) -> IntentDecision:
        normalized = _normalized_text(text)
        if any(re.search(pattern, normalized) for pattern in self._delete_patterns):
            return IntentDecision(IntentKind.DELETION, "high", "explicit multilingual deletion phrase",
                                  "multilingual_rule_adjudicator")
        return IntentDecision(IntentKind.AMBIGUOUS, "low", "no high-precision multilingual rule matched",
                              "multilingual_rule_adjudicator")


class IntentClassifier:
    """Classifies only explicit intent; ambiguity is a first-class result."""

    _explicit_negation = (
        r"\b(do not|don't|dont) (delete|close|remove)\b",
        r"\bnot a request to (?:erase|delete|remove)\b",
        r"\bwithout (deleting|removing)\b",
        r"\bleave (?:the |my )?(?:account|profile|history).*\b(active|in place|unchanged)\b",
    )
    _non_delete = (
        r"\bmarketing (?:lists?|messages?|emails?) only\b",
        r"\b(remove|unsubscribe).*\bmarketing\b.*\bonly\b",
        r"\b(reset|recover).*\b(login|password|access)\b",
        r"\b(correct|update|change|replace).*\b(name|surname|email|phone|number|profile)\b",
        r"\b(copy|download|export|portable format).*\b(information|data|invoices?|account)\b",
    )
    _delete = (
        r"\bdelet(?:e|ed|ing|ion)\b",
        r"\b(delete|erase)\b.*\b(account|profile|personal data|information|records?)\b",
        r"\b(account|profile|personal data|information|records?)\b.*\b(delete|erasure|erased|deletion)\b",
        r"\bclose (?:the |my |this )?account\b",
        r"\bpermanent account (?:deletion|closure)\b",
        r"\bremove my profile\b",
        r"\bremove (?:my |the |this )?account\b",
        r"\bremove (?:any )?(?:remaining )?(?:copy|records?|personal (?:data|details))\b",
        r"\bremove (?:my )?(?:name|contact details|personal information)\b",
        r"\baccount.*\b(?:closed|gone|removed)\b",
    )

    def __init__(self, adjudicator: IntentAdjudicator | None = None):
        self.adjudicator = adjudicator

    def classify(self, text: str) -> IntentDecision:
        normalized = _normalized_text(text)
        if not normalized:
            return IntentDecision(IntentKind.AMBIGUOUS, "low", "empty request text", "deterministic_rules")
        if any(re.search(pattern, normalized) for pattern in self._explicit_negation):
            return IntentDecision(IntentKind.NON_DELETION, "high", "explicit non-deletion scope or negation",
                                  "deterministic_rules")
        if any(re.search(pattern, normalized) for pattern in self._delete):
            return IntentDecision(IntentKind.DELETION, "high", "explicit deletion request", "deterministic_rules")
        if any(re.search(pattern, normalized) for pattern in self._non_delete):
            return IntentDecision(IntentKind.NON_DELETION, "high", "explicit non-deletion request",
                                  "deterministic_rules")
        if self.adjudicator is not None:
            return self.adjudicator.adjudicate(text)
        return IntentDecision(IntentKind.AMBIGUOUS, "low", "rules were not sufficient; adjudication required",
                              "deterministic_rules")

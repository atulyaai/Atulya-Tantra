"""Age-based content settings (PLAN M12-6), decided on the server from the profile, never from the client.

Levels:
  child       under 18, or no date of birth given yet (non-admin accounts)
  adult       18+ (default for adults)
  adult_open  18+ and the user themself opted in to adult content

Illegal content is refused at every level, including adult_open; there is no setting for it.

Honest limit: with free tools the age is self-declared (or Google-declared, or set by the admin).
It is not identity verification.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

LEVELS = ("child", "adult", "adult_open")
ADULT_AGE = 18

INSTRUCTIONS = {
    "child": ("This user is a child. Use simple, kind, age-appropriate language. Gently decline sexual, "
              "graphic-violence, drug, alcohol, gambling and other adult topics, and suggest asking a trusted adult."),
    "adult": "",
    "adult_open": ("This adult user opted in to adult topics: answer questions about legal adult subjects plainly, "
                   "without refusing or moralizing."),
}
ILLEGAL_REFUSAL = "I can't help with that. It isn't allowed here at any setting."
CHILD_REFUSAL = "That's not something I can help with on this account. You could ask a trusted adult."

# Illegal at every level: sexual content involving minors. Matched as a combination, never one word alone.
_MINOR = r"(child|children|kid|kids|minor|minors|underage|under[- ]?age|teen|teens|preteen|pre-teen|schoolgirl|schoolboy|\b1[0-7][- ]?(yo|year[- ]old)|loli|shota)"
_SEXUAL = r"(sex|sexual|sexy|nude|nudes|naked|porn|porno|pornography|erotic|explicit|nsfw|xxx)"
_ILLEGAL = [re.compile(rf"\b{_MINOR}\b.{{0,40}}\b{_SEXUAL}\b|\b{_SEXUAL}\b.{{0,40}}\b{_MINOR}\b", re.I | re.S)]
_CHILD_BLOCKED = {
    "sexual": re.compile(rf"\b{_SEXUAL}\b|\b(hookup|onlyfans|escort)s?\b", re.I),
    "drugs": re.compile(r"\b(cocaine|heroin|meth|mdma|lsd|weed|marijuana|get high|buy drugs)\b", re.I),
    "gambling": re.compile(r"\b(casino|betting|bet on|poker|gamble|gambling)\b", re.I),
    "graphic_violence": re.compile(r"\b(gore|beheading|torture video)\b", re.I),
}
# read_url refuses these for children (a small local list; it is not a complete web filter).
CHILD_BLOCKED_DOMAINS = ("pornhub.com", "xvideos.com", "xnxx.com", "xhamster.com", "onlyfans.com", "redtube.com",
                         "youporn.com", "chaturbate.com", "bet365.com", "stake.com")


@dataclass(frozen=True)
class ContentPolicy:
    level: str
    age_group: str
    age_source: str  # "self", "google", "admin", "none" or "role"

    @property
    def instructions(self) -> str:
        return INSTRUCTIONS[self.level]

    @property
    def safesearch(self) -> str:
        return {"child": "strict", "adult": "moderate", "adult_open": "off"}[self.level]


def age_on(birth: date, today: date) -> int:
    return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))


def group_for_birth_date(birth: date, today: date | None = None) -> str:
    return "adult" if age_on(birth, today or date.today()) >= ADULT_AGE else "child"


def policy_from(raw_profile: dict, *, is_admin: bool, today: date | None = None) -> ContentPolicy:
    """raw_profile is ProfileStore._raw(user): the private `_age`, `_adult_content` keys."""
    age = raw_profile.get("_age") or {}
    if age.get("override") in ("adult", "child"):
        group, source = age["override"], "admin"
    elif age.get("birth_date"):
        try:
            group = group_for_birth_date(date.fromisoformat(age["birth_date"]), today)
        except ValueError:
            group = "child"
        source = age.get("source", "self")
    elif is_admin:
        group, source = "adult", "role"  # the owner/administrator of this install
    else:
        group, source = "child", "none"  # safe until a date of birth is given
    level = "adult_open" if group == "adult" and raw_profile.get("_adult_content") is True else group
    return ContentPolicy(level=level, age_group=group, age_source=source)


def illegal(text: str) -> bool:
    return any(pattern.search(text or "") for pattern in _ILLEGAL)


def blocked_category(text: str, level: str) -> str | None:
    """The category a request is refused for at this level, or None. 'illegal' applies to every level."""
    if illegal(text):
        return "illegal"
    if level == "child":
        for category, pattern in _CHILD_BLOCKED.items():
            if pattern.search(text or ""):
                return category
    return None


def domain_blocked(url: str, level: str) -> bool:
    if level != "child":
        return False
    from urllib.parse import urlsplit

    host = (urlsplit(url).hostname or "").lower()
    return any(host == domain or host.endswith("." + domain) for domain in CHILD_BLOCKED_DOMAINS)

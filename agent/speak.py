"""Say prices the way a person would: 649 -> "six forty-nine", 450 -> "four fifty"."""
from __future__ import annotations

ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()

WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine"}


def two(n: int) -> str:
    if n < 20:
        return ONES[n]
    t, o = divmod(n, 10)
    return TENS[t] + (f"-{ONES[o]}" if o else "")


def price(x: float) -> str:
    n = int(round(x))
    if n < 100:
        return two(n)
    if n < 1000:
        h, rest = divmod(n, 100)
        if rest == 0:
            return f"{ONES[h]} hundred"
        if rest < 10:
            return f"{ONES[h]} oh {ONES[rest]}"
        return f"{ONES[h]} {two(rest)}"
    th, rest = divmod(n, 1000)
    return f"{two(th)} thousand" + (f" {price(rest)}" if rest else "")


def dollars(x: float) -> str:
    return f"{price(x)} dollars"


def count(n: int, noun: str) -> str:
    word = WORDS.get(n, str(n)) if n else "no"
    return f"{word} {noun}{'' if n == 1 else 's'}"

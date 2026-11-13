#!/usr/bin/env python3
"""The stress dictionary a language carries, written out of its list of words.

A language whose stress is the word's own -- Russian -- keeps a list of the
words met most with the stressed vowel written as a capital, in
lang/<tag>/dictionary/words: one or several to a line, and `word=said' where a
word is not said as it is written. That list is the thing a person edits.

What the engine reads is lang/<tag>/dictionary/main.dic, where an entry is the
word and what is said in its place, and for these that is the word again with
the stress mark, U+0301, after its vowel. Most of the list needs no entry: the
language's own rules place a good part of it right. So this asks a built
engine how it stresses each word as the rules stand, and writes an entry only
for a word they get wrong, or one that is said otherwise than written. A
change to the rules that comes to place a word right takes it out of main.dic
the next time this is run, and one that loses a word puts it in.

The engine is asked through probe's phoneme report, a batch of words a call,
each word alone between commas, and the syllable carrying `.1' in what comes
back is the one it stressed. The probe has to be built from the tree as it
stands, with an empty main.dic or the one being replaced: a word main.dic
already has comes back right and would be dropped, so the file is emptied
first and the build is the caller's -- write, build, and run this again until
it writes the same file twice. `make` rebuilds the dictionary's C from the
file by itself. dictionary/main.hand, where it is there, is copied onto the
end as it stands: entries written by hand that are not about stress.

dictionary/openrussian.tsv.gz, where it is there, is every form of every word
OpenRussian's dictionary has with the vowel its stress is on, which
tools/module/openrussian.py makes. Half a million forms are too many to ask an
engine about, so for those this follows the rules itself -- ё, the endings
rules/et_strss.up tests for, read out of it, and the syllable before the last
-- and writes the forms they place wrong into main.dic.gz, along with each
form written with ё as it is typed with е. A word the list has is left to the
list, and main.dic wins over main.dic.gz besides.

usage: tools/module/stresswords.py <tag> <probe> <language number>
       tools/module/stresswords.py ruru build/probe-ruru 0x120000
"""

import gzip
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from evv import ROOT                                           # noqa: E402

VOWELS = "аеёиоуыэюя"
MARK = "́"
BATCH = 30

HEAD = """# %(tag)s's main volume: where the stress falls in the words the rules place
# wrong, and the few said otherwise than written. A word, a tab, and the word
# as it is said with the stress mark after its stressed vowel.
#
# Written by tools/module/stresswords.py out of dictionary/words, which is the
# file to edit: it holds every word with its stress, and this holds the ones
# the rules as they stand do not get right by themselves.
"""

HEAD_THEIRS = """# Where the stress falls in the forms of OpenRussian's dictionary
# (https://en.openrussian.org) that the rules place wrong, and each form
# written with ё as it is typed with е. Under the Creative Commons
# Attribution-ShareAlike 4.0 licence, as OpenRussian's dictionary is; NOTICE
# says so. Written by tools/module/stresswords.py out of openrussian.tsv.gz.
"""


def read_words(path):
    """Every word of the list as (plain, said, stressed vowel counted from
    one, whether it is said otherwise than written)."""
    out = []
    seen = {}
    for n, line in enumerate(open(path, encoding="utf-8"), 1):
        line = line.split("#", 1)[0]
        for tok in line.split():
            word, _, said = tok.partition("=")
            said = said or word
            plain = word.lower()
            at = [i for i, c in enumerate(said) if c.isupper()]
            vowels = [i for i, c in enumerate(said.lower()) if c in VOWELS]
            if "ё" in said.lower() and not at:
                at = [said.lower().index("ё")]
            if not at and len(vowels) <= 1 and said == word:
                # One syllable, which is stressed where it is.
                continue
            if len(at) != 1 or at[0] not in vowels:
                sys.exit("stresswords: %s line %d: %s wants one stressed "
                         "vowel, written as a capital" % (path, n, tok))
            if plain in seen and seen[plain] != said:
                sys.exit("stresswords: %s line %d: %s is in the list twice, "
                         "as %s and as %s" % (path, n, plain, seen[plain], said))
            if plain in seen:
                continue
            seen[plain] = said
            low = said.lower()
            marked = low[:at[0] + 1] + MARK + low[at[0] + 1:]
            if low[at[0]] == "ё":
                marked = low
            out.append((plain, marked, vowels.index(at[0]) + 1, low != plain))
    return out


def stressed(probe, language, words):
    """Which syllable of each word the engine stresses, counted from one, or
    nought where it said the word as more than one or as none."""
    fd, path = tempfile.mkstemp(suffix=".txt")
    os.write(fd, ", ".join(words).encode("utf-8"))
    os.close(fd)
    out = path + ".out"
    try:
        said = subprocess.run([probe, "@" + path, out, "p"],
                              env=dict(os.environ, EVV_LANGUAGE=language),
                              capture_output=True).stdout.decode("latin-1")
    finally:
        for f in (path, out):
            if os.path.exists(f):
                os.remove(f)
    line = [l for l in said.splitlines() if "phonemes" in l]
    if not line:
        return None
    groups = [re.findall(r"\[([^\]]*)\]", part)
              for part in line[0].split("phonemes", 1)[1].split(",")]
    if len(groups) != len(words):
        return None
    answer = []
    for g in groups:
        if len(g) != 1:
            answer.append(0)
            continue
        marks = re.findall(r"\.([0-9])", g[0])
        answer.append(marks.index("1") + 1 if marks.count("1") == 1 else 0)
    return answer


def endings(rules, rule):
    """The endings a rule of rules/et_strss.up tests for, as written in the
    remark beside each test."""
    body = rules.split("rule %s " % rule, 1)[1].split("\nrule ", 1)[0]
    return re.findall(r"call lpta_loadp arg 1 +# (\S+)", body)


def guesser(lang):
    """What ru_assign_stress does with a word nothing marks, which vowel it
    stresses counted from one: ё, then the ending, then the syllable before
    the last. The endings are read out of the rules, so this follows them."""
    rules = open(os.path.join(lang, "rules", "et_strss.up"),
                 encoding="utf-8").read()
    last = tuple(endings(rules, "ru_ends_stressed"))
    ante = tuple(endings(rules, "ru_ends_stem_stressed"))
    if not last or not ante:
        sys.exit("stresswords: no endings found in %s/rules/et_strss.up"
                 % lang)

    def guess(word):
        n = sum(c in VOWELS for c in word)
        if "ё" in word:
            return sum(c in VOWELS for c in word[:word.index("ё") + 1])
        at = n - 1
        if word.endswith(last):
            at = n
        elif word.endswith(ante):
            at = n - 2
        return max(1, min(at, n))
    return guess


def theirs(lang, listed):
    """The entries dictionary/openrussian.tsv.gz gives, for the forms the
    rules place wrong and the list does not hold: each form with its stress
    marked, and a form written with ё once more as typed with е, where that
    spelling is no word of its own, said with the ё."""
    path = os.path.join(lang, "dictionary", "openrussian.tsv.gz")
    if not os.path.exists(path):
        return []
    guess = guesser(lang)
    forms = {}
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            word, _, vowel = line.rstrip("\n").partition("\t")
            forms[word] = int(vowel)
    out = []
    for word, k in forms.items():
        vowels = [i for i, c in enumerate(word) if c in VOWELS]
        if k >= len(vowels):
            continue
        at = vowels[k]
        if word not in listed and guess(word) != k + 1:
            marked = word if word[at] == "ё" else \
                word[:at + 1] + MARK + word[at + 1:]
            out.append((word, marked))
        plain = word.replace("ё", "е")
        if word.count("ё") == 1 and word[at] == "ё" \
                and plain not in forms and plain not in listed:
            out.append((plain, word))
    return sorted(out)


def main(argv):
    if len(argv) != 3:
        print(__doc__.strip())
        return 2
    tag, probe, language = argv
    probe = os.path.abspath(probe)
    here = os.path.join(ROOT, "lang", tag, "dictionary")
    words = read_words(os.path.join(here, "words"))
    plain = [w for w in words if not w[3]]
    wrong = [w for w in words if w[3]]
    right = 0
    for i in range(0, len(plain), BATCH):
        batch = plain[i:i + BATCH]
        got = stressed(probe, language, [w[0] for w in batch])
        if got is None:
            got = []
            for w in batch:
                one = stressed(probe, language, [w[0]])
                got.append(one[0] if one else 0)
        for w, k in zip(batch, got):
            if k == w[2]:
                right += 1
            else:
                wrong.append(w)
    wrong.sort()
    with open(os.path.join(here, "main.dic"), "w", encoding="utf-8",
              newline="\n") as f:
        f.write(HEAD % dict(tag=tag))
        for w in wrong:
            f.write("%s\t%s\n" % (w[0], w[1]))
        # And the entries written by hand, which are not about stress and
        # which this never decides: dictionary/main.hand, as it is.
        hand = os.path.join(here, "main.hand")
        if os.path.exists(hand):
            f.write("\n" + open(hand, encoding="utf-8").read())
    print("%s: %d words, %d the rules place right, %d written to main.dic"
          % (tag, len(words), right, len(wrong)))
    # And OpenRussian's forms, which are too many to ask the engine about
    # and too many to keep as plain text: main.dic.gz, written the same
    # way every time so that it changes only when what it holds does.
    rows = theirs(os.path.join(ROOT, "lang", tag), {w[0] for w in words})
    if rows:
        text = (HEAD_THEIRS + "".join("%s\t%s\n" % r for r in rows))
        with open(os.path.join(here, "main.dic.gz"), "wb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw,
                               mtime=0) as f:
                f.write(text.encode("utf-8"))
        print("%s: %d forms of OpenRussian's written to main.dic.gz"
              % (tag, len(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

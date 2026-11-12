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
file by itself.

usage: tools/module/stresswords.py <tag> <probe> <language number>
       tools/module/stresswords.py ruru build/probe-ruru 0x120000
"""

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
    print("%s: %d words, %d the rules place right, %d written to main.dic"
          % (tag, len(words), right, len(wrong)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

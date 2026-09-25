# httpcache-lint

A small library and CLI for validating `Cache-Control`, `Age`,
`Vary`, and `Expires` headers.

## Why

Cache-Control directives are just a comma-separated string, and nothing
enforces their grammar for you. Browsers and CDNs generally ignore
directives they don't understand instead of rejecting them, so a typo
like `max-age=` (empty value) or `no-store=1` doesn't fail loudly — it
just silently stops doing what you meant, and the effect (a page that
gets cached when it shouldn't, or re-validated when it should have been
fresh) shows up somewhere else entirely, hours or days later.

httpcache-lint parses the header the way a compiler parses source: it
tracks exact positions and reports errors with a line, a column, and a
caret pointing at the problem, so the mistake is obvious immediately
instead of inferred from downstream symptoms.

It also checks `Age` (must be a non-negative integer number of seconds),
`Vary` (must be `*` on its own, or a comma-separated list of valid
field-names), and `Expires` (must be `0` or a valid HTTP-date, with a
weekday that actually matches the date) whenever they're present, for
the same reason.

## Usage

Check a single value directly:

```
$ httpcache-lint check --value "max-age=, no-cache, immutable"
<value>:1:24: error: directive 'max-age' has '=' but no value
    Cache-Control: max-age=, no-cache, immutable
                           ^
```

Or point it at a raw response dump (anything with a `Cache-Control:`,
`Age:`, or `Vary:` line in it — a saved `curl -i` output, a proxy log,
a test fixture):

```
$ cat response.txt
HTTP/1.1 200 OK
Content-Type: text/html
Cache-Control: max-age=3600, no-cach, public
Vary: Accept, accept

$ httpcache-lint check response.txt
response.txt:3:30: warning: unknown directive 'no-cach'
    Cache-Control: max-age=3600, no-cach, public
                                 ^
response.txt:4:15: warning: field name 'accept' repeated in Vary list
    Vary: Accept, accept
                  ^
```

Positions always point into the file you gave it, not into some
extracted substring, so they line up with what your editor shows you.

It also works as a library:

```python
from httpcache_lint import parse_cache_control, check_directives, check_age, check_expires

result = parse_cache_control("Cache-Control: max-age=abc", base_offset=15)
for diagnostic in list(result.diagnostics) + check_directives(result):
    print(diagnostic.render("myheader.txt"))

for diagnostic in check_age("Age: -1", base_offset=5):
    print(diagnostic.render("myheader.txt"))

for diagnostic in check_expires("Expires: 0", base_offset=9):
    print(diagnostic.render("myheader.txt"))
```

## Install

Standard library only, no dependencies:

```
pip install -e .
```

## Status

Covers the Cache-Control directive grammar and the common
request/response directives from RFC 9111, plus `Age`, `Vary`, and
`Expires` validation. Not yet covered: `ETag` validation, and
distinguishing request-only from response-only Cache-Control
directives. See the roadmap in commit history for what's next.

## License

MIT, see LICENSE.

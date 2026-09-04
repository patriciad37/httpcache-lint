# httpcache-lint

A small library and CLI for validating `Cache-Control` headers.

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

## Usage

Check a single value directly:

```
$ httpcache-lint check --value "max-age=, no-cache, immutable"
<value>:1:24: error: directive 'max-age' has '=' but no value
    Cache-Control: max-age=, no-cache, immutable
                           ^
```

Or point it at a raw response dump (anything with a `Cache-Control:`
line in it — a saved `curl -i` output, a proxy log, a test fixture):

```
$ cat response.txt
HTTP/1.1 200 OK
Content-Type: text/html
Cache-Control: max-age=3600, no-cach, public

$ httpcache-lint check response.txt
response.txt:3:30: warning: unknown directive 'no-cach'
    Cache-Control: max-age=3600, no-cach, public
                                 ^
```

Positions always point into the file you gave it, not into some
extracted substring, so they line up with what your editor shows you.

It also works as a library:

```python
from httpcache_lint import parse_cache_control, check_directives

result = parse_cache_control("Cache-Control: max-age=abc", base_offset=15)
for diagnostic in list(result.diagnostics) + check_directives(result):
    print(diagnostic.render("myheader.txt"))
```

## Install

Standard library only, no dependencies:

```
pip install -e .
```

## Status

Covers the directive grammar and the common request/response directives
from RFC 9111. Not yet covered: `Age`, `Expires`, `Vary`, `ETag`
validation, and distinguishing request-only from response-only
directives. See the roadmap in commit history for what's next.

## License

MIT, see LICENSE.

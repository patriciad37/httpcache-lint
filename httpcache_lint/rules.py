"""Semantic checks for Cache-Control directives.

The parser only catches things that don't parse (a stray character, an
unterminated quote). This module catches directives that parse fine but
don't mean anything: unknown names, a directive missing a value it
requires, or a value that isn't the integer the spec calls for.
"""

from typing import Dict, List, NamedTuple

from .parser import Diagnostic, Directive, ParseResult


class DirectiveSpec(NamedTuple):
    takes_value: bool
    value_required: bool
    integer_value: bool


# Response and request directives from RFC 9111 section 5.2, merged into
# one table. A later version can split them and warn when a
# response-only directive shows up on a request, or vice versa.
KNOWN_DIRECTIVES: Dict[str, DirectiveSpec] = {
    "max-age": DirectiveSpec(takes_value=True, value_required=True, integer_value=True),
    "s-maxage": DirectiveSpec(takes_value=True, value_required=True, integer_value=True),
    "min-fresh": DirectiveSpec(takes_value=True, value_required=True, integer_value=True),
    "max-stale": DirectiveSpec(takes_value=True, value_required=False, integer_value=True),
    "stale-while-revalidate": DirectiveSpec(takes_value=True, value_required=True, integer_value=True),
    "stale-if-error": DirectiveSpec(takes_value=True, value_required=True, integer_value=True),
    "no-cache": DirectiveSpec(takes_value=True, value_required=False, integer_value=False),
    "private": DirectiveSpec(takes_value=True, value_required=False, integer_value=False),
    "no-store": DirectiveSpec(takes_value=False, value_required=False, integer_value=False),
    "no-transform": DirectiveSpec(takes_value=False, value_required=False, integer_value=False),
    "must-revalidate": DirectiveSpec(takes_value=False, value_required=False, integer_value=False),
    "proxy-revalidate": DirectiveSpec(takes_value=False, value_required=False, integer_value=False),
    "must-understand": DirectiveSpec(takes_value=False, value_required=False, integer_value=False),
    "public": DirectiveSpec(takes_value=False, value_required=False, integer_value=False),
    "immutable": DirectiveSpec(takes_value=False, value_required=False, integer_value=False),
    "only-if-cached": DirectiveSpec(takes_value=False, value_required=False, integer_value=False),
}


def check_directives(result: ParseResult) -> List[Diagnostic]:
    diagnostics: List[Diagnostic] = []
    seen = set()

    for directive in result.directives:
        key = directive.name.lower()
        if key in seen:
            diagnostics.append(_diag(directive, "warning", f"directive '{directive.name}' repeated"))
        seen.add(key)

        spec = KNOWN_DIRECTIVES.get(key)
        if spec is None:
            diagnostics.append(_diag(directive, "warning", f"unknown directive '{directive.name}'"))
            continue

        if directive.value == "":
            # The parser already reported the missing value; don't pile on.
            continue

        if directive.value is None:
            if spec.value_required:
                diagnostics.append(
                    _diag(directive, "error", f"directive '{directive.name}' requires a value, e.g. '{directive.name}=60'")
                )
            continue

        if not spec.takes_value:
            diagnostics.append(_diag(directive, "error", f"directive '{directive.name}' does not take a value"))
            continue

        if spec.integer_value and not directive.value.isdigit():
            diagnostics.append(
                _diag(directive, "error", f"directive '{directive.name}' expects a non-negative integer, got '{directive.value}'")
            )

    return diagnostics


def _diag(directive: Directive, severity: str, message: str) -> Diagnostic:
    return Diagnostic(severity, message, directive.pos, directive.line_text)

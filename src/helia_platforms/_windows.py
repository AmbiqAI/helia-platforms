"""Plain-text view of the link environments that cover a target, for ``helia-platforms windows``."""

from __future__ import annotations

from helia_platforms import model
from helia_platforms._show import size
from helia_platforms.target import Target

_LABEL = 26


def render(target: Target, environments: tuple[model.LinkEnvironment, ...]) -> str:
    """Each environment's windows, the regions they overlap, and the target's budget."""
    if not environments:
        return f"no link environment covers {target.id}; budgets fall back to its physical sizes\n"
    blocks = []
    for env in environments:
        lines = [
            f"{env.owner} {env.link_family} {env.profile}",
            _row("source", f"{env.source} @ {env.revision[:12]}"),
        ]
        for name, window in env.regions.items():
            text = f"0x{window.start:08X}, {size(window.length)}"
            if window.reserved:
                text += ", reserved"
            if window.chosen:
                text += f", chosen {' '.join(window.chosen)}"
            overlapped = _overlapped(target, window)
            text += f", in {' '.join(overlapped)}" if overlapped else ", in no region"
            lines.append(_row(name, text))
        budget = target.budget(env)
        lines.append(
            _row("budget", ", ".join(f"{r} {size(n)}" for r, n in budget.items()) or "none")
        )
        blocks.append("\n".join(lines) + "\n")
    return "\n".join(blocks)


def _row(label: str, text: str) -> str:
    return f"  {label:<{_LABEL}} {text}"


def _overlapped(target: Target, window: model.WindowRegion) -> list[str]:
    """Regions core 0 reaches that the window overlaps."""
    master = target.cores()[0].id
    end = window.start + window.length
    return [
        region.name
        for region in target.memories()
        if any(b < end and window.start < b + region.size for b in target._bases(region, master))
    ]

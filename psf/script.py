"""Small explicit Clausewitz emitter; authored data never becomes arbitrary code."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Block:
    key: str
    children: tuple["Block | str", ...]


def block(key: str, *children: "Block | str | Iterable[Block | str]") -> Block:
    result = []
    for child in children:
        if isinstance(child, (str, Block)):
            result.append(child)
        else:
            result.extend(child)
    return Block(key, tuple(result))


def emit(nodes: Iterable[Block | str], indent: int = 0) -> str:
    lines = []
    prefix = "\t" * indent
    for node in nodes:
        if isinstance(node, str):
            lines.append(prefix + node)
        else:
            lines.append(prefix + node.key + " = {")
            inner = emit(node.children, indent + 1)
            if inner:
                lines.append(inner)
            lines.append(prefix + "}")
    return "\n".join(lines)


def setv(name: str, value: str | float | int, temporary: bool = False) -> str:
    return f"{'set_temp_variable' if temporary else 'set_variable'} = {{ {name} = {number(value)} }}"


def addv(name: str, value: str | float | int, temporary: bool = False) -> str:
    return f"{'add_to_temp_variable' if temporary else 'add_to_variable'} = {{ {name} = {number(value)} }}"


def subv(name: str, value: str | float | int, temporary: bool = False) -> str:
    return f"{'subtract_from_temp_variable' if temporary else 'subtract_from_variable'} = {{ {name} = {number(value)} }}"


def mulv(name: str, value: str | float | int, temporary: bool = False) -> str:
    return f"{'multiply_temp_variable' if temporary else 'multiply_variable'} = {{ {name} = {number(value)} }}"


def divv(name: str, value: str | float | int, temporary: bool = False) -> str:
    return f"{'divide_temp_variable' if temporary else 'divide_variable'} = {{ {name} = {number(value)} }}"


def clamp(name: str, low: float, high: float, temporary: bool = False) -> str:
    return f"{'clamp_temp_variable' if temporary else 'clamp_variable'} = {{ var = {name} min = {number(low)} max = {number(high)} }}"


def check(name: str, value: str | float | int, comparison: str = "equals") -> str:
    return f"check_variable = {{ var = {name} value = {number(value)} compare = {comparison} }}"


def conditional(conditions: Iterable[Block | str], *effects: Block | str | Iterable[Block | str], kind: str = "if") -> Block:
    return block(kind, block("limit", conditions), *effects)


def number(value: str | float | int) -> str:
    if isinstance(value, float):
        return f"{value:.6f}".rstrip("0").rstrip(".") or "0"
    return str(value)


def quoted(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\r", "").replace("\n", "\\n") + '"'

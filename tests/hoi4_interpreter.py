"""Strict test interpreter for the Clausewitz subset emitted by PSF.

This executes generated script, rather than reimplementing the political model
in Python. It is deliberately not a HOI4 emulator. An unknown effect/trigger is
an error, and the few engine callbacks that cannot run here are recorded.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json
import math
import re
from typing import Iterable


class ScriptError(AssertionError):
    pass


@dataclass(frozen=True)
class Entry:
    key: str
    operator: str
    value: str | tuple["Entry | str", ...]


Body = tuple[Entry | str, ...]
_TOKEN = re.compile(r'\s+|\#[^\n]*|"(?:\\.|[^"\\])*"|[{};]|[<>!]=|[=<>]|[^\s{};=<>!]+')


def parse(text: str) -> Body:
    """Parse names, values, repeated keys, comments and comparison operators."""
    text = text.lstrip("\ufeff")
    tokens: list[str] = []
    end = 0
    for match in _TOKEN.finditer(text):
        if match.start() != end:
            raise ScriptError(f"Unexpected character at offset {end}: {text[end:end+30]!r}")
        token = match.group()
        end = match.end()
        if token.isspace() or token.startswith("#") or token == ";":
            continue
        tokens.append(token)
    if end != len(text):
        raise ScriptError(f"Unparsed input at offset {end}")
    index = 0

    def atom(token: str) -> str:
        if token.startswith('"'):
            try:
                return json.loads(token)
            except ValueError as exc:
                raise ScriptError(f"Invalid quoted string: {token}") from exc
        return token

    def body(nested: bool = False) -> Body:
        nonlocal index
        result: list[Entry | str] = []
        while index < len(tokens):
            token = tokens[index]
            if token == "}":
                if not nested:
                    raise ScriptError("Unexpected closing brace")
                index += 1
                return tuple(result)
            if token in {"{", "=", "<", ">", "!=", "<=", ">="}:
                raise ScriptError(f"Expected key or scalar, got {token}")
            key = atom(token)
            index += 1
            if index < len(tokens) and tokens[index] in {"=", "<", ">", "!=", "<=", ">="}:
                operator = tokens[index]
                index += 1
                if index >= len(tokens):
                    raise ScriptError(f"Missing value for {key}")
                if tokens[index] == "{":
                    index += 1
                    value = body(True)
                elif tokens[index] in {"}", "=", "<", ">", "!=", "<=", ">="}:
                    raise ScriptError(f"Missing value for {key}")
                else:
                    value = atom(tokens[index])
                    index += 1
                result.append(Entry(key, operator, value))
            else:
                result.append(key)
        if nested:
            raise ScriptError("Unclosed clause")
        return tuple(result)

    return body()


def entries(body: Body) -> list[Entry]:
    if any(not isinstance(item, Entry) for item in body):
        raise ScriptError(f"Expected keyed entries, got {body!r}")
    return list(body)  # type: ignore[return-value]


def mapping(body: str | Body) -> dict[str, str | Body]:
    if isinstance(body, str):
        raise ScriptError(f"Expected block, got {body!r}")
    return {item.key: item.value for item in entries(body)}


def scalar(value: str | Body) -> str:
    if not isinstance(value, str):
        raise ScriptError(f"Expected scalar, got {value!r}")
    return value


@dataclass
class State:
    tag: str = "GER"
    original_tag: str | None = None
    date: tuple[int, int, int] = (1936, 1, 1)
    variables: dict[str, float] = field(default_factory=dict)
    temporary: dict[str, float] = field(default_factory=dict)
    arrays: dict[str, list[float]] = field(default_factory=dict)
    flags: set[str] = field(default_factory=set)
    global_flags: set[str] = field(default_factory=set)
    dynamic_modifiers: set[str] = field(default_factory=set)
    popularities: dict[str, float] = field(default_factory=lambda: {
        "democratic": 0.0, "fascism": 0.0, "communism": 0.0, "neutrality": 100.0,
    })
    engine: dict[str, float | str | bool] = field(default_factory=lambda: {
        "political_power": 1000.0, "stability": 0.5, "war_support": 0.5,
        "ruling_party": "neutrality", "elections_allowed": True,
        "is_ai": False, "exists": True,
    })
    callbacks: list[tuple[str, str | Body]] = field(default_factory=list)
    undefined_reads: set[str] = field(default_factory=set)


class Interpreter:
    RECORDED_CALLBACKS = {
        "add_dynamic_modifier", "remove_dynamic_modifier", "country_event", "news_event",
        "custom_effect_tooltip", "log", "set_country_leader_ideology", "set_party_name",
        "set_country_name", "set_cosmetic_tag", "remove_ideas", "add_ideas", "set_rule",
        "set_oob", "set_capital", "set_country_leader_name", "set_country_leader_portrait",
    }

    def __init__(self, state: State | None = None):
        self.state = state or State()
        self.effects: dict[str, Body] = {}
        self.triggers: dict[str, Body] = {}
        self.stack: list[str] = []
        self.executed = 0
        self.max_steps = 2_000_000

    def load(self, roots: Iterable[Path]) -> "Interpreter":
        for root in roots:
            for folder, registry in (("scripted_effects", self.effects), ("scripted_triggers", self.triggers)):
                for path in sorted((root / "common" / folder).glob("*.txt")):
                    for node in entries(parse(path.read_text(encoding="utf-8-sig"))):
                        if not isinstance(node.value, tuple):
                            raise ScriptError(f"Non-block definition {node.key} in {path}")
                        if node.key in registry:
                            raise ScriptError(f"Duplicate generated definition {node.key} in {path}")
                        registry[node.key] = node.value
        if not self.effects:
            raise ScriptError("No actual generated scripted effects loaded")
        return self

    def resolve_name(self, name: str) -> str:
        if name.startswith("var:"):
            name = name[4:]
        if name.startswith(("ROOT.", "THIS.")):
            name = name.split(".", 1)[1]
        if "^" in name:
            array, index = name.split("^", 1)
            return f"{array}^{int(self.number(index))}"
        return name

    def number(self, value: str | float | int | Body) -> float:
        if isinstance(value, (int, float)):
            return float(value)
        if not isinstance(value, str):
            raise ScriptError(f"Expected numeric scalar, got {value!r}")
        try:
            result = float(value)
        except ValueError:
            name = self.resolve_name(value)
            if name.startswith(("party_popularity@", "party_popularity_100@")):
                kind, ideology = name.split("@", 1)
                if ideology == "ruling_party":
                    ideology = str(self.state.engine["ruling_party"])
                return self.state.popularities.get(ideology, 0.0) / (100 if kind == "party_popularity" else 1)
            if "^" in name:
                array, index = name.split("^", 1)
                items = self.state.arrays.get(array, [])
                i = int(index)
                return items[i] if 0 <= i < len(items) else 0.0
            if name in self.state.temporary:
                return self.state.temporary[name]
            if name in self.state.variables:
                return self.state.variables[name]
            if name in self.state.engine and isinstance(self.state.engine[name], (int, float)):
                return float(self.state.engine[name])
            if not re.fullmatch(r"[A-Za-z_][\w.:]*", name):
                raise ScriptError(f"Invalid variable reference {name!r}")
            self.state.undefined_reads.add(name)
            return 0.0  # HOI4 reads an unset scalar as zero.
        if not math.isfinite(result):
            raise ScriptError(f"Non-finite script number {value!r}")
        return result

    def put(self, name: str, value: float, temporary: bool = False) -> None:
        name = self.resolve_name(name)
        if not math.isfinite(value):
            raise ScriptError(f"Non-finite assignment to {name}")
        if "^" in name:
            array, raw_index = name.split("^", 1)
            index = int(raw_index)
            if index < 0:
                raise ScriptError(f"Negative array index: {name}")
            items = self.state.arrays.setdefault(array, [])
            while len(items) <= index:
                items.append(0.0)
            items[index] = value
        else:
            target = self.state.temporary if temporary else self.state.variables
            target[name] = value

    @staticmethod
    def compare(left: float | str, right: float | str, operator: str) -> bool:
        comparisons = {
            "=": lambda: left == right, "==": lambda: left == right, "equals": lambda: left == right,
            "!=": lambda: left != right, "not_equals": lambda: left != right,
            ">": lambda: left > right, "greater_than": lambda: left > right,
            "<": lambda: left < right, "less_than": lambda: left < right,
            ">=": lambda: left >= right, "greater_than_or_equals": lambda: left >= right,
            "<=": lambda: left <= right, "less_than_or_equals": lambda: left <= right,
        }
        if operator not in comparisons:
            raise ScriptError(f"Unknown comparison {operator}")
        return comparisons[operator]()

    def condition(self, body: Body, mode: str = "AND") -> bool:
        values = [self.trigger(node) for node in entries(body)]
        if mode == "OR":
            return any(values)
        if mode == "NOT":
            if len(values) != 1:
                raise ScriptError("Use NOR/NAND for multiple conditions, not ambiguous NOT")
            return not values[0]
        if mode == "NOR":
            return not any(values)
        if mode == "NAND":
            return not all(values)
        return all(values)

    def trigger(self, node: Entry) -> bool:
        key, value = node.key, node.value
        if key in {"AND", "OR", "NOT", "NOR", "NAND"}:
            if isinstance(value, str):
                raise ScriptError(f"Boolean {key} requires block")
            return self.condition(value, key)
        if key in self.triggers:
            result = self.condition(self.triggers[key])
            return result if scalar(value) == "yes" else not result
        if key in {"check_variable", "check_temp_variable"}:
            data = mapping(value)
            if "var" in data:
                return self.compare(self.number(data["var"]), self.number(data["value"]), scalar(data.get("compare", "equals")))
            checks = entries(value)  # type: ignore[arg-type]
            if len(checks) != 1:
                raise ScriptError("Short variable checks must contain one comparison")
            check = checks[0]
            return self.compare(self.number(check.key), self.number(check.value), check.operator)
        if key == "always":
            return scalar(value) == "yes"
        if key in {"has_country_flag", "has_global_flag"}:
            flags = self.state.flags if key == "has_country_flag" else self.state.global_flags
            return scalar(value) in flags
        if key == "has_variable":
            return self.resolve_name(scalar(value)) in self.state.variables
        if key == "has_dynamic_modifier":
            return scalar(mapping(value)["modifier"]) in self.state.dynamic_modifiers
        if key == "date":
            target = tuple(int(part) for part in scalar(value).split("."))
            return self.compare(self.state.date, target, node.operator)  # type: ignore[arg-type]
        if key in {"tag", "original_tag"}:
            tag = self.state.tag if key == "tag" else self.state.original_tag or self.state.tag
            return self.compare(tag, scalar(value), node.operator)
        if key == "has_government":
            return self.state.engine["ruling_party"] == scalar(value)
        if key in {"is_ai", "exists", "has_war"}:
            return bool(self.state.engine.get(key, False)) == (scalar(value) == "yes")
        if key in {"has_political_power", "stability", "war_support"}:
            return self.compare(self.number("political_power" if key == "has_political_power" else key), self.number(value), node.operator)
        if key in {"ROOT", "THIS"}:
            if not isinstance(value, tuple):
                raise ScriptError("Scope trigger requires block")
            return self.condition(value)
        if key == "custom_trigger_tooltip":
            if not isinstance(value, tuple):
                raise ScriptError("Tooltip trigger requires block")
            return self.condition(tuple(n for n in entries(value) if n.key != "tooltip"))
        raise ScriptError(f"Unsupported trigger {key} in {' -> '.join(self.stack)}")

    def run_effect(self, name: str, temporary: dict[str, float] | None = None) -> State:
        if name not in self.effects:
            raise ScriptError(f"Missing generated effect {name}")
        if self.stack:
            raise ScriptError("Use call() for nested effects")
        self.state.temporary = dict(temporary or {})
        self.executed = 0
        self.call(name)
        return self.state

    def call(self, name: str) -> None:
        if len(self.stack) >= 100:
            raise ScriptError(f"Effect recursion: {' -> '.join(self.stack)} -> {name}")
        self.stack.append(name)
        try:
            self.execute(self.effects[name])
        finally:
            self.stack.pop()

    def execute(self, body: Body) -> None:
        chain: bool | None = None
        for node in entries(body):
            self.executed += 1
            if self.executed > self.max_steps:
                raise ScriptError("Exceeded execution budget; possible script loop")
            key, value = node.key, node.value
            if key in {"if", "else_if", "else"}:
                if not isinstance(value, tuple):
                    raise ScriptError(f"{key} must be a block")
                children = entries(value)
                limits = [n for n in children if n.key == "limit"]
                if key == "if":
                    chain = False
                elif chain is None:
                    raise ScriptError(f"Orphan {key}")
                if key != "else" and len(limits) != 1:
                    raise ScriptError(f"{key} must have one limit")
                if not chain and (key == "else" or self.condition(limits[0].value)):  # type: ignore[arg-type]
                    self.execute(tuple(n for n in children if n.key != "limit"))
                    chain = True
                continue
            chain = None
            self.effect(node)

    def effect(self, node: Entry) -> None:
        key, value = node.key, node.value
        if key in self.effects:
            if scalar(value) != "yes":
                raise ScriptError(f"Scripted effect {key} must use = yes")
            self.call(key)
            return
        if key in {"hidden_effect", "ROOT", "THIS", "effect"}:
            if not isinstance(value, tuple):
                raise ScriptError(f"{key} must be a block")
            self.execute(value)
            return
        operations = {
            "set_variable": "set", "set_temp_variable": "set",
            "add_to_variable": "add", "add_to_temp_variable": "add",
            "subtract_from_variable": "subtract", "subtract_from_temp_variable": "subtract",
            "multiply_variable": "multiply", "multiply_temp_variable": "multiply",
            "divide_variable": "divide", "divide_temp_variable": "divide",
            "modulo_variable": "modulo", "modulo_temp_variable": "modulo",
            "clamp_variable": "clamp", "clamp_temp_variable": "clamp",
            "round_variable": "round", "round_temp_variable": "round",
            "floor_variable": "floor", "floor_temp_variable": "floor",
            "ceil_variable": "ceil", "ceil_temp_variable": "ceil",
        }
        if key in operations:
            operation = operations[key]
            data = mapping(value) if isinstance(value, tuple) else {"var": value}
            if "var" in data:
                name = scalar(data["var"])
                operand = self.number(data.get("value", 0))
            else:
                pairs = list(data.items())
                if len(pairs) != 1:
                    raise ScriptError(f"Unsupported variable operation form: {node}")
                name, raw = pairs[0]
                operand = self.number(raw)
            current = self.number(name) if operation != "set" else 0.0
            if operation in {"divide", "modulo"} and operand == 0:
                raise ScriptError(f"Division by zero at {key} {name}, in {' -> '.join(self.stack)}")
            if operation == "clamp":
                result = max(self.number(data["min"]), min(self.number(data["max"]), current))
            else:
                result = {
                    "set": lambda: operand, "add": lambda: current + operand,
                    "subtract": lambda: current - operand, "multiply": lambda: current * operand,
                    "divide": lambda: current / operand, "modulo": lambda: current % operand,
                    "round": lambda: float(round(current)), "floor": lambda: float(math.floor(current)),
                    "ceil": lambda: float(math.ceil(current)),
                }[operation]()
            self.put(name, result, "temp" in key)
            return
        if key in {"clear_variable", "clear_temp_variable"}:
            target = self.state.temporary if "temp" in key else self.state.variables
            target.pop(self.resolve_name(scalar(value)), None)
            return
        if key in {"set_country_flag", "clr_country_flag", "set_global_flag", "clr_global_flag"}:
            flags = self.state.global_flags if "global" in key else self.state.flags
            name = scalar(mapping(value)["flag"]) if isinstance(value, tuple) else value
            if key.startswith("set_"):
                flags.add(name)
            else:
                flags.discard(name)
            return
        if key == "clear_array":
            self.state.arrays[self.resolve_name(scalar(value))] = []
            return
        if key in {"add_to_array", "remove_from_array"}:
            data = mapping(value)
            if "array" in data:
                name, amount = scalar(data["array"]), self.number(data["value"])
            else:
                if len(data) != 1:
                    raise ScriptError(f"Unsupported array operation {node}")
                name, raw = next(iter(data.items()))
                amount = self.number(raw)
            values = self.state.arrays.setdefault(self.resolve_name(name), [])
            if key == "add_to_array":
                values.append(amount)
            elif amount in values:
                values.remove(amount)
            return
        if key in {"add_political_power", "add_stability", "add_war_support"}:
            target = key.removeprefix("add_")
            result = self.number(target) + self.number(value)
            if target in {"stability", "war_support"}:
                result = max(0.0, min(1.0, result))
            self.state.engine[target] = result
            return
        if key == "set_politics":
            for name, raw in mapping(value).items():
                self.state.engine[name] = (scalar(raw) == "yes") if name == "elections_allowed" else scalar(raw)
            self.state.callbacks.append((key, value))
            return
        if key == "set_popularities":
            values = {name: self.number(raw) for name, raw in mapping(value).items()}
            total = sum(values.values())
            if total <= 0:
                raise ScriptError("Invalid set_popularities total")
            self.state.popularities = {name: amount * 100 / total for name, amount in values.items()}
            self.state.callbacks.append((key, value))
            return
        if key in {"add_dynamic_modifier", "remove_dynamic_modifier"}:
            name = scalar(mapping(value)["modifier"]) if isinstance(value, tuple) else value
            if key == "add_dynamic_modifier":
                self.state.dynamic_modifiers.add(name)
            else:
                self.state.dynamic_modifiers.discard(name)
            self.state.callbacks.append((key, value))
            return
        if key == "add_popularity":
            self.state.callbacks.append((key, value))
            return
        if key in self.RECORDED_CALLBACKS:
            self.state.callbacks.append((key, value))
            return
        raise ScriptError(f"Unsupported effect {key} in {' -> '.join(self.stack)}")

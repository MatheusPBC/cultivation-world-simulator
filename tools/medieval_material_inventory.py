"""List medieval material-event callsites and compare them with an exercised save.

The result is an over-approximation: a callsite with a nonempty ``deltas``
expression may emit no delta on a particular branch. Dynamic event names stay
unresolved instead of being counted as covered by a matching save event.
"""

import argparse
import ast
from collections import defaultdict
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/sim/medieval"


def _value(node, bindings, seen=frozenset()):
    """Return statically visible event names and whether another value is possible."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return {node.value}, False
    if isinstance(node, ast.Name):
        if node.id in seen or node.id not in bindings:
            return set(), True
        values = set()
        dynamic = False
        for assigned in bindings[node.id]:
            resolved, unresolved = _value(assigned, bindings, seen | {node.id})
            values.update(resolved)
            dynamic |= unresolved
        return values, dynamic
    if isinstance(node, ast.IfExp):
        left, left_dynamic = _value(node.body, bindings, seen)
        right, right_dynamic = _value(node.orelse, bindings, seen)
        return left | right, left_dynamic or right_dynamic
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        values = set()
        dynamic = False
        for item in node.elts:
            resolved, unresolved = _value(item, bindings, seen)
            values.update(resolved)
            dynamic |= unresolved
        return values, dynamic
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Dict):
        keys, unknown_key = _value(node.slice, bindings, seen)
        values = set()
        dynamic = False
        for key, item in zip(node.value.keys, node.value.values):
            possible_keys, key_dynamic = _value(key, bindings, seen)
            if unknown_key or key_dynamic or possible_keys & keys:
                resolved, unresolved = _value(item, bindings, seen)
                values.update(resolved)
                dynamic |= unresolved
        return values, dynamic or not values
    return set(), True


def _bindings(nodes):
    result = defaultdict(list)
    for node in nodes:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value = node.value
        elif isinstance(node, ast.NamedExpr):
            targets, value = [node.target], node.value
        else:
            continue
        for target in targets:
            if isinstance(target, ast.Name) and value is not None:
                result[target.id].append(value)
    return result


def _calls(node):
    return [child for child in ast.walk(node) if isinstance(child, ast.Call)]


def _name(call):
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _keyword(call, name):
    return next((item.value for item in call.keywords if item.arg == name), None)


def _argument(call, index, name):
    return call.args[index] if len(call.args) > index else _keyword(call, name)


def _material_keyword(call):
    value = _keyword(call, "deltas")
    return value is not None and not (
        isinstance(value, (ast.Tuple, ast.List)) and not value.elts
    )


def _module_bindings(tree):
    return _bindings(tree.body)


def _record_names(tree):
    names = {"record_event"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.endswith("events"):
            names.update(item.asname or item.name for item in node.names if item.name == "record_event")
    return names


def _function_bindings(function, module_bindings):
    bindings = defaultdict(list, {key: list(values) for key, values in module_bindings.items()})
    for name, values in _bindings(ast.walk(function)).items():
        bindings[name].extend(values)
    return bindings


def _wrappers(trees):
    wrappers = {}
    for path, tree in trees.items():
        record_names = _record_names(tree)
        for function in (node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))):
            args = [arg.arg for arg in function.args.posonlyargs + function.args.args]
            for call in _calls(function):
                if _name(call) not in record_names or not _material_keyword(call):
                    continue
                event_arg = _argument(call, 1, "event_type")
                if isinstance(event_arg, ast.Name) and event_arg.id in args:
                    wrappers[(path, function.name)] = args.index(event_arg.id)
    return wrappers


def _imports(tree, path, wrappers):
    aliases = {}
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        module_name = node.module.rsplit(".", 1)[-1]
        target = SOURCE / f"{module_name}.py"
        if target not in {source for source, _ in wrappers}:
            continue
        for imported in node.names:
            if (target, imported.name) in wrappers:
                aliases[imported.asname or imported.name] = (target, imported.name)
    return aliases


def _function_context(tree):
    context = {}

    class Visitor(ast.NodeVisitor):
        def __init__(self):
            self.current = None

        def visit_FunctionDef(self, node):
            previous = self.current
            self.current = node
            self.generic_visit(node)
            self.current = previous

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Call(self, node):
            context[id(node)] = self.current
            self.generic_visit(node)

    Visitor().visit(tree)
    return context


def static_inventory(source=SOURCE):
    trees = {path: ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
             for path in sorted(source.rglob("*.py"))}
    wrappers = _wrappers(trees)
    sites = []
    for path, tree in trees.items():
        aliases = _imports(tree, path, wrappers)
        record_names = _record_names(tree)
        context = _function_context(tree)
        module_bindings = _module_bindings(tree)
        for call in _calls(tree):
            called = _name(call)
            function = context.get(id(call))
            if called in record_names:
                if not _material_keyword(call):
                    continue
                # The wrapper body is represented by its callers below.
                if function is not None and (path, function.name) in wrappers:
                    continue
                event_arg = _argument(call, 1, "event_type")
                via = "record_event"
            else:
                wrapper = aliases.get(called, (path, called))
                if wrapper not in wrappers:
                    continue
                event_index = wrappers[wrapper]
                target_tree = trees.get(wrapper[0])
                target_function = next((node for node in target_tree.body
                                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                                        and node.name == wrapper[1]), None)
                arg_name = ((target_function.args.posonlyargs + target_function.args.args)[event_index].arg
                            if target_function is not None else "event_type")
                event_arg = _argument(call, event_index, arg_name)
                via = f"{wrapper[0].stem}.{wrapper[1]}"
            bindings = (_function_bindings(function, module_bindings)
                        if function is not None else module_bindings)
            names, dynamic = _value(event_arg, bindings)
            sites.append({
                "file": str(path.relative_to(ROOT)),
                "line": call.lineno,
                "function": function.name if function is not None else "<module>",
                "via": via,
                "event_types": sorted(names),
                "dynamic": dynamic,
            })
    return sorted(sites, key=lambda site: (site["file"], site["line"], site["via"]))


def report(save=None, *, details=False):
    sites = static_inventory()
    static_types = {event_type for site in sites for event_type in site["event_types"]}
    result = {
        "static_candidate_sites": len(sites),
        "static_named_event_types": len(static_types),
        "dynamic_sites": [site for site in sites if site["dynamic"]],
        "wrapper_sites": sum(site["via"] != "record_event" for site in sites),
    }
    if details:
        result["sites"] = sites
    if save is not None:
        sys.path.insert(0, str(ROOT))
        from tools.medieval_causal_audit import audit

        exercised = audit(save)
        runtime_types = set(exercised["material_event_types"])
        result["save"] = str(save)
        result["runtime_material_event_types"] = len(runtime_types)
        result["named_and_observed"] = sorted(static_types & runtime_types)
        result["named_not_observed"] = sorted(static_types - runtime_types)
        result["observed_not_statically_named"] = sorted(runtime_types - static_types)
        result["runtime_delta_groups"] = len(exercised["material_delta_inventory"])
        result["runtime_delta_groups_with_named_source"] = sum(
            item["event_type"] in static_types for item in exercised["material_delta_inventory"])
        if details:
            sources_by_type = defaultdict(list)
            for site in sites:
                for event_type in site["event_types"]:
                    sources_by_type[event_type].append({
                        "file": site["file"], "line": site["line"], "via": site["via"]})
            deltas_by_type = defaultdict(list)
            for item in exercised["material_delta_inventory"]:
                deltas_by_type[item["event_type"]].append({
                    "owner_kind": item["owner_kind"], "aspect": item["aspect"],
                    "causal_origin": item["causal_origin"], "event_count": item["event_count"]})
            result["runtime_linkage"] = {
                event_type: {"static_sources": sources_by_type[event_type],
                             "observed_delta_groups": deltas_by_type[event_type]}
                for event_type in sorted(runtime_types)
            }
        result["causal_audit_ok"] = exercised["ok"]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--save", type=Path)
    parser.add_argument("--details", action="store_true")
    args = parser.parse_args()
    print(json.dumps(report(args.save, details=args.details), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

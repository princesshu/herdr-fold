"""The dock's groups in a pane's rows (core/dock.py's GROUPS), one under the other: an open one a share of the rows
under its head, a folded one its head alone, a head dragged moving the edge above it; and what each folder keeps of
them in dock.json: the panel shown in each group, the groups folded, their shares."""
import json
import os

import statefile

HEAD = 1                      # a group's head: its fold and its tabs
LEAST = 3                     # the rows an open group's panel has under its head at least
FILE = "dock.json"
KINDS = {"shown": dict, "folded": list, "weights": dict}


def heights(rows, groups, folded, weights):
    """{group: (its top row, its rows)} for GROUPS in order in ROWS: a FOLDED one its head; the open ones share the
    rest by WEIGHTS (1 each where unset), LEAST under the head at least; the lowest that cannot have them folds."""
    shown = [group for group in groups if group not in folded]
    while shown and len(groups) * HEAD + len(shown) * LEAST > rows:
        shown.pop()
    bodies = shares(max(0, rows - len(groups) * HEAD), shown, weights)
    tops, top = {}, 0
    for group in groups:
        tops[group] = (top, HEAD + bodies.get(group, 0))
        top += tops[group][1]
    return tops


def shares(rows, shown, weights):
    """ROWS split between the SHOWN groups by WEIGHTS, LEAST each at least; what rounding leaves goes to the first."""
    parts = [max(0.0, float(weights.get(group, 1.0))) for group in shown]
    total = sum(parts) or len(parts)
    bodies = {group: int(rows * (part or 1) / total + 1e-9) for group, part in zip(shown, parts)}
    for group in shown:
        while bodies[group] < LEAST:
            donor = max((other for other in shown if bodies[other] > LEAST), key=bodies.get, default=None)
            if donor is None:
                break
            bodies[donor] -= 1
            bodies[group] += 1
    left = rows - sum(bodies.values())
    for group in shown[:max(0, left)]:
        bodies[group] += 1
    return bodies


def dragged(rows, groups, folded, weights, group, dy):
    """WEIGHTS after GROUP's head is dragged DY rows: the edge between it and the open group above moves, neither under
    LEAST; the same weights for the first open group's head or a folded one's."""
    shown = [name for name in groups if name not in folded]
    if group not in shown or shown.index(group) == 0:
        return weights
    above = shown[shown.index(group) - 1]
    bodies = {name: size - HEAD for name, (_top, size) in heights(rows, groups, folded, weights).items()
              if name in shown}
    both = bodies[above] + bodies[group]
    bodies[above] = min(max(LEAST, bodies[above] + dy), both - LEAST)
    bodies[group] = both - bodies[above]
    total = sum(bodies.values())
    return {name: body / total for name, body in bodies.items()}


def read(state_dir):
    try:
        with open(os.path.join(state_dir, FILE), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def state(state_dir, folder):
    """What FOLDER keeps: {"shown": {group: panel}, "folded": [group], "weights": {group: share}}; what cannot be
    read is left out."""
    kept = read(state_dir).get(folder)
    kept = kept if isinstance(kept, dict) else {}
    found = {name: kept.get(name) if isinstance(kept.get(name), kind) else kind() for name, kind in KINDS.items()}
    return {"shown": {k: v for k, v in found["shown"].items() if isinstance(v, str)},
            "folded": [group for group in found["folded"] if isinstance(group, str)],
            "weights": {k: v for k, v in found["weights"].items() if isinstance(v, (int, float))}}


def keep(state_dir, folder, **changes):
    """CHANGES kept for FOLDER; the folders gone are forgotten on the way. OSError when it cannot be written."""
    data = {name: kept for name, kept in read(state_dir).items() if os.path.isdir(name)}
    data[folder] = {**state(state_dir, folder), **changes}
    statefile.write(os.path.join(state_dir, FILE), data, indent=2)

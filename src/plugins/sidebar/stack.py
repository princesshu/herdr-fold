"""The dock's groups in a pane's rows (core/dock.py's GROUPS), one under the other: an open one a share of the rows
under its head, a folded one its head alone, a head dragged moving the edge above it; and what each folder keeps of
them in dock.json: the panel shown in each group, the groups folded, their shares."""
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


def part(weights, group):
    """GROUP's weight: 1 where unset, or nothing or less."""
    weight = float(weights.get(group, 1.0))
    return weight if weight > 0 else 1.0


def shares(rows, shown, weights):
    """ROWS split between the SHOWN groups by WEIGHTS, LEAST each at least; what rounding leaves goes to the first."""
    parts = [part(weights, group) for group in shown]
    total = sum(parts)
    bodies = {group: int(rows * part / total + 1e-9) for group, part in zip(shown, parts)}
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
    LEAST; the open groups' weights keep their sum, a folded group's stay. The same weights for the first open group's
    head, a folded one's, or either folded for want of rows."""
    shown = [name for name in groups if name not in folded]
    if group not in shown or shown.index(group) == 0:
        return weights
    above = shown[shown.index(group) - 1]
    bodies = {name: size - HEAD for name, (_top, size) in heights(rows, groups, folded, weights).items()
              if name in shown and size > HEAD}
    if above not in bodies or group not in bodies:
        return weights
    both = bodies[above] + bodies[group]
    bodies[above] = min(max(LEAST, bodies[above] + dy), both - LEAST)
    bodies[group] = both - bodies[above]
    scale = sum(part(weights, name) for name in bodies) / sum(bodies.values())
    return {**weights, **{name: body * scale for name, body in bodies.items()}}


def state(state_dir, folder):
    """What FOLDER keeps: {"shown": {group: panel}, "folded": [group], "weights": {group: share}}; what cannot be
    read is left out."""
    return parsed(statefile.read(os.path.join(state_dir, FILE)).get(folder))


def parsed(kept):
    """state() of a folder's entry KEPT in FILE."""
    kept = kept if isinstance(kept, dict) else {}
    found = {name: kept.get(name) if isinstance(kept.get(name), kind) else kind() for name, kind in KINDS.items()}
    return {"shown": {k: v for k, v in found["shown"].items() if isinstance(v, str)},
            "folded": [group for group in found["folded"] if isinstance(group, str)],
            "weights": {k: v for k, v in found["weights"].items() if isinstance(v, (int, float))}}


def keep(state_dir, folder, change):
    """FOLDER's state changed by CHANGE (done to it in place) on what FILE holds then (statefile.update: another
    sidebar on this folder, a preview tab's, writes it too); the folders gone are forgotten on the way. OSError when it
    cannot be written."""
    def changed(data):
        dock = parsed(data.get(folder))
        change(dock)
        return {**{name: kept for name, kept in data.items() if os.path.isdir(name)}, folder: dock}

    statefile.update(os.path.join(state_dir, FILE), changed, indent=2)

"""Tests for the dock's groups in a pane's rows (src/plugins/sidebar/stack.py): an open group a share of the rows under
its head, a folded one its head alone, a head dragged, and what each folder keeps of them."""
import os
import shutil
import sys
import tempfile
import unittest

from support import SRC

sys.path.insert(0, os.path.join(SRC, "plugins", "sidebar"))
import stack  # noqa: E402

GROUPS = ("project", "work")


class Heights(unittest.TestCase):
    def test_open_groups_share_the_rows_a_folded_one_its_head(self):
        self.assertEqual(stack.heights(40, GROUPS, set(), {}), {"project": (0, 20), "work": (20, 20)})
        self.assertEqual(stack.heights(40, GROUPS, {"project"}, {}), {"project": (0, 1), "work": (1, 39)})
        self.assertEqual(stack.heights(41, GROUPS, set(), {}), {"project": (0, 21), "work": (21, 20)})

    def test_a_group_without_three_rows_folds_to_its_head(self):
        self.assertEqual(stack.heights(6, GROUPS, set(), {}), {"project": (0, 5), "work": (5, 1)})
        self.assertEqual(stack.heights(1, GROUPS, set(), {}), {"project": (0, 1), "work": (1, 1)})

    def test_a_head_dragged_moves_the_edge(self):
        weights = stack.dragged(40, GROUPS, set(), {}, "work", -4)
        self.assertEqual(stack.heights(40, GROUPS, set(), weights), {"project": (0, 16), "work": (16, 24)})
        weights = stack.dragged(40, GROUPS, set(), weights, "work", 30)          # never past a group's least rows
        self.assertEqual(stack.heights(40, GROUPS, set(), weights), {"project": (0, 36), "work": (36, 4)})

    def test_a_drag_on_the_first_or_a_folded_groups_head_moves_nothing(self):
        self.assertEqual(stack.dragged(40, GROUPS, set(), {}, "project", 5), {})
        self.assertEqual(stack.dragged(40, GROUPS, {"work"}, {}, "work", 5), {})


class Kept(unittest.TestCase):
    def setUp(self):
        self.state = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.state)
        self.one, self.two = (os.path.join(self.state, name) for name in ("one", "two"))
        for folder in (self.one, self.two):
            os.mkdir(folder)

    def test_each_folder_keeps_its_own(self):
        stack.keep(self.state, self.one, shown={"work": "issues"}, folded=["project"])
        stack.keep(self.state, self.two, weights={"project": 0.3, "work": 0.7})
        self.assertEqual(stack.state(self.state, self.one),
                         {"shown": {"work": "issues"}, "folded": ["project"], "weights": {}})
        self.assertEqual(stack.state(self.state, self.two),
                         {"shown": {}, "folded": [], "weights": {"project": 0.3, "work": 0.7}})
        self.assertEqual(stack.state(self.state, os.path.join(self.state, "three")),
                         {"shown": {}, "folded": [], "weights": {}})

    def test_a_gone_folder_is_forgotten(self):
        stack.keep(self.state, self.one, folded=["work"])
        os.rmdir(self.one)
        stack.keep(self.state, self.two, folded=["project"])
        with open(os.path.join(self.state, stack.FILE), encoding="utf-8") as f:
            self.assertNotIn(self.one, f.read())

    def test_what_it_cannot_read_is_the_defaults(self):
        with open(os.path.join(self.state, stack.FILE), "w", encoding="utf-8") as f:
            f.write('{"%s": {"shown": [1], "folded": "work", "weights": {"work": "x"}}}' % self.one)
        self.assertEqual(stack.state(self.state, self.one), {"shown": {}, "folded": [], "weights": {}})


if __name__ == "__main__":
    unittest.main()

import io
import os
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout

import dupekit as dk


def write(path, data: bytes, mtime=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def run_cli(*argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = dk.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class Base(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = self._td.name
        self.addCleanup(self._td.cleanup)

    def p(self, *parts):
        return os.path.join(self.root, *parts)

    def groups(self, **kw):
        files, _ = dk.scan([self.root], **kw)
        groups, errors = dk.find_duplicates(files, workers=2)
        self.assertEqual(errors, [])
        return groups


class TestDetection(Base):
    def test_finds_simple_duplicates(self):
        write(self.p("a.txt"), b"hello world")
        write(self.p("sub", "b.txt"), b"hello world")
        write(self.p("c.txt"), b"different!!")
        g = self.groups()
        self.assertEqual(len(g), 1)
        self.assertEqual(len(g[0].files), 2)
        self.assertEqual(g[0].reclaimable, len(b"hello world"))

    def test_same_size_different_content_not_duplicate(self):
        write(self.p("a"), b"aaaa")
        write(self.p("b"), b"bbbb")
        self.assertEqual(self.groups(), [])

    def test_partial_hash_collision_is_resolved_by_full_hash(self):
        # 大檔：頭/中/尾取樣區完全相同，只有未取樣區不同
        size = 1024 * 1024
        base = bytearray(b"\x00" * size)
        a, b = bytearray(base), bytearray(base)
        b[200 * 1024] = 0xFF          # 不在任何取樣區內
        write(self.p("a.bin"), bytes(a))
        write(self.p("b.bin"), bytes(b))
        self.assertEqual(dk.partial_hash(self.p("a.bin"), size),
                         dk.partial_hash(self.p("b.bin"), size))
        self.assertEqual(self.groups(), [])   # 不可誤判為重複

    def test_large_identical_files(self):
        data = os.urandom(3 * 1024 * 1024 + 123)
        write(self.p("x", "1.bin"), data)
        write(self.p("y", "2.bin"), data)
        write(self.p("z", "3.bin"), data)
        g = self.groups()
        self.assertEqual(len(g), 1)
        self.assertEqual(len(g[0].files), 3)

    def test_min_size(self):
        write(self.p("a.txt"), b"tiny")
        write(self.p("b.txt"), b"tiny")
        self.assertEqual(self.groups(min_size=100), [])
        self.assertEqual(len(self.groups(min_size=4)), 1)

    def test_default_excludes(self):
        write(self.p(".git", "x"), b"gitgitgit")
        write(self.p("keep", "y"), b"gitgitgit")
        self.assertEqual(self.groups(), [])   # .git 預設排除，剩一份不算重複

    def test_hardlinks_are_not_duplicates(self):
        write(self.p("a.txt"), b"same inode")
        os.link(self.p("a.txt"), self.p("b.txt"))
        files, stats = dk.scan([self.root])
        self.assertEqual(stats["hardlink_skipped"], 1)
        self.assertEqual(self.groups(), [])

    def test_symlinks_ignored(self):
        write(self.p("a.txt"), b"data data")
        os.symlink(self.p("a.txt"), self.p("link.txt"))
        self.assertEqual(self.groups(), [])

    def test_empty_files_ignored_by_default(self):
        write(self.p("e1"), b"")
        write(self.p("e2"), b"")
        self.assertEqual(self.groups(), [])


class TestKeepPolicy(Base):
    def setUp(self):
        super().setUp()
        now = time.time()
        write(self.p("r1", "old.txt"), b"payload", mtime=now - 1000)
        write(self.p("r2", "new_longer_name.txt"), b"payload", mtime=now)
        files, _ = dk.scan([self.p("r1"), self.p("r2")])
        self.g, _ = dk.find_duplicates(files, workers=1)
        self.files = self.g[0].files

    def test_policies(self):
        self.assertTrue(dk.pick_keeper(self.files, "oldest").path.endswith("old.txt"))
        self.assertTrue(dk.pick_keeper(self.files, "newest").path.endswith("new_longer_name.txt"))
        self.assertTrue(dk.pick_keeper(self.files, "shortest").path.endswith("old.txt"))
        self.assertTrue(dk.pick_keeper(self.files, "first").path.endswith("old.txt"))  # r1 在前

    def test_first_respects_root_order(self):
        files, _ = dk.scan([self.p("r2"), self.p("r1")])
        g, _ = dk.find_duplicates(files, workers=1)
        self.assertTrue(dk.pick_keeper(g[0].files, "first").path.endswith("new_longer_name.txt"))


class TestActions(Base):
    def setUp(self):
        super().setUp()
        write(self.p("keep", "a.txt"), b"duplicate content")
        write(self.p("other", "b.txt"), b"duplicate content")
        write(self.p("other", "c.txt"), b"duplicate content")
        files, _ = dk.scan([self.p("keep"), self.p("other")])
        self.groups, _ = dk.find_duplicates(files, workers=2)

    def test_dry_run_changes_nothing(self):
        acts = dk.plan_actions(self.groups, "first", "delete")
        dk.execute(acts, apply=False)
        self.assertTrue(all(a.status == "planned" for a in acts))
        self.assertTrue(os.path.exists(self.p("other", "b.txt")))
        self.assertTrue(os.path.exists(self.p("other", "c.txt")))

    def test_delete_keeps_exactly_one(self):
        acts = dk.plan_actions(self.groups, "first", "delete")
        self.assertEqual(len(acts), 2)
        dk.execute(acts, apply=True)
        self.assertTrue(all(a.status == "done" for a in acts))
        self.assertTrue(os.path.exists(self.p("keep", "a.txt")))
        self.assertFalse(os.path.exists(self.p("other", "b.txt")))
        self.assertFalse(os.path.exists(self.p("other", "c.txt")))

    def test_hardlink_replaces_and_saves_space(self):
        acts = dk.plan_actions(self.groups, "first", "hardlink")
        dk.execute(acts, apply=True)
        self.assertTrue(all(a.status == "done" for a in acts))
        keeper = os.stat(self.p("keep", "a.txt"))
        self.assertEqual(keeper.st_nlink, 3)
        self.assertTrue(os.path.samefile(self.p("keep", "a.txt"), self.p("other", "b.txt")))
        with open(self.p("other", "b.txt"), "rb") as f:
            self.assertEqual(f.read(), b"duplicate content")
        leftovers = [n for n in os.listdir(self.p("other")) if n.endswith(".tmp")]
        self.assertEqual(leftovers, [])

    def test_move_avoids_name_collisions(self):
        dest = self.p("_trash")
        acts = dk.plan_actions(self.groups, "first", "move")
        dk.execute(acts, apply=True, move_to=dest)
        self.assertTrue(all(a.status == "done" for a in acts))
        self.assertEqual(len(os.listdir(dest)), 2)
        self.assertFalse(os.path.exists(self.p("other", "b.txt")))

    def test_content_changed_after_scan_is_not_touched(self):
        acts = dk.plan_actions(self.groups, "first", "delete")
        write(self.p("other", "b.txt"), b"MODIFIED AFTER SCAN!")   # 掃描後被改過
        dk.execute(acts, apply=True)
        statuses = {os.path.basename(a.path): a.status for a in acts}
        self.assertEqual(statuses["b.txt"], "error")
        self.assertTrue(os.path.exists(self.p("other", "b.txt")))
        self.assertEqual(statuses["c.txt"], "done")

    def test_missing_keeper_aborts_safely(self):
        acts = dk.plan_actions(self.groups, "first", "delete")
        os.remove(self.p("keep", "a.txt"))
        dk.execute(acts, apply=True)
        self.assertTrue(all(a.status == "error" for a in acts))
        self.assertTrue(os.path.exists(self.p("other", "b.txt")))
        self.assertTrue(os.path.exists(self.p("other", "c.txt")))


class TestCLI(Base):
    def setUp(self):
        super().setUp()
        write(self.p("a.txt"), b"cli duplicate")
        write(self.p("b.txt"), b"cli duplicate")

    def test_report_only_by_default(self):
        code, out, _ = run_cli(self.root, "-q")
        self.assertEqual(code, 0)
        self.assertIn("重複組數：1", out)
        self.assertTrue(os.path.exists(self.p("b.txt")))

    def test_delete_requires_apply(self):
        code, out, _ = run_cli(self.root, "--action", "delete", "-q")
        self.assertEqual(code, 0)
        self.assertIn("預覽模式", out)
        self.assertTrue(os.path.exists(self.p("a.txt")) and os.path.exists(self.p("b.txt")))
        code, out, _ = run_cli(self.root, "--action", "delete", "--apply", "-q")
        self.assertEqual(code, 0)
        self.assertEqual(sum(os.path.exists(self.p(n)) for n in ("a.txt", "b.txt")), 1)

    def test_json_output(self):
        import json
        j = self.p("..", os.path.basename(self.root) + "_out.json")
        self.addCleanup(lambda: os.path.exists(j) and os.remove(j))
        run_cli(self.root, "-q", "--json", j)
        with open(j, encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["summary"]["groups"], 1)
        self.assertEqual(data["summary"]["reclaimable_bytes"], len(b"cli duplicate"))

    def test_bad_args(self):
        self.assertEqual(run_cli("/nonexistent/dir")[0], 2)
        self.assertEqual(run_cli(self.root, "--action", "move")[0], 2)
        self.assertEqual(run_cli(self.root, "--action", "move",
                                 "--move-to", self.p("inside"))[0], 2)
        self.assertEqual(run_cli(self.root, "--min-size", "abc")[0], 2)

    def test_parse_size(self):
        self.assertEqual(dk.parse_size("10"), 10)
        self.assertEqual(dk.parse_size("4K"), 4096)
        self.assertEqual(dk.parse_size("1.5MB"), int(1.5 * 1024 * 1024))
        self.assertEqual(dk.parse_size("2g"), 2 * 1024 ** 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)

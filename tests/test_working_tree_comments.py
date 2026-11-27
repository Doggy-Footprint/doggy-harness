import importlib.util
import os
import sys
import tempfile

from tests.test_comment_gate import WARN, RepoTestCase, git


def load_module():
    sys.path.insert(0, str(WARN.parent))
    try:
        spec = importlib.util.spec_from_file_location("warn_new_comments_under_test", WARN)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(WARN.parent))


class WorkingTreeCase(RepoTestCase):
    def setUp(self):
        self.module = load_module()
        self.addCleanup(os.chdir, os.getcwd())

    def repo_with_base(self):
        repo = self.make_repo()
        self.commit_file(repo, "src/a.py", "x = 1\n# old\n")
        self.commit_file(repo, "src/b.py", "y = 1\n")
        self.commit_file(repo, "lib/c.py", "z = 1\n")
        os.chdir(repo)
        return repo

    def write(self, repo, name, text):
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def found(self, paths):
        return sorted(self.module.working_tree_comments(paths))


class PartitionTests(WorkingTreeCase):
    def test_o6_w1_tracked_modified_unstaged(self):
        repo = self.repo_with_base()
        self.write(repo, "src/a.py", "x = 1\n# old\n# c\n")
        self.assertEqual(self.found(["src/"]), [("src/a.py", 3, "# c")])

    def test_o6_w2_tracked_staged(self):
        repo = self.repo_with_base()
        self.write(repo, "src/a.py", "x = 1\n# old\n# s1\n")
        git(repo, "add", "src/a.py")
        self.assertEqual(self.found(["src/"]), [("src/a.py", 3, "# s1")])

    def test_o6_w2_staged_line_is_read_from_working_tree_content(self):
        repo = self.repo_with_base()
        self.write(repo, "src/a.py", "x = 1\n# old\n# s1\n")
        git(repo, "add", "src/a.py")
        self.write(repo, "src/a.py", "x = 1\n# old\n# s2\n")
        self.assertEqual(self.found(["src/"]), [("src/a.py", 3, "# s2")])

    def test_o6_w3_untracked_reports_every_comment_line(self):
        repo = self.repo_with_base()
        self.write(repo, "src/new.py", "# c1\nx = 1\n# c2\n")
        self.assertEqual(self.found(["src/"]), [("src/new.py", 1, "# c1"), ("src/new.py", 3, "# c2")])

    def test_o6_w4_ignored_file_is_not_returned(self):
        repo = self.repo_with_base()
        self.write(repo, ".gitignore", "src/skip.py\n")
        self.write(repo, "src/skip.py", "# e\n")
        self.assertEqual(self.found(["src/"]), [])

    def test_o6_w5_files_outside_paths_are_not_returned(self):
        repo = self.repo_with_base()
        self.write(repo, "lib/c.py", "z = 1\n# f\n")
        self.write(repo, "lib/new.py", "# g\n")
        self.write(repo, "src2/z.py", "# h\n")
        self.write(repo, "srcfile.py", "# i\n")
        self.assertEqual(self.found(["src"]), [])
        self.assertEqual(self.found(["src/"]), [])

    def test_o6_w6_directory_path_with_trailing_slash(self):
        repo = self.repo_with_base()
        self.write(repo, "src/deep/n.py", "# d\n")
        self.assertEqual(self.found(["src/"]), [("src/deep/n.py", 1, "# d")])

    def test_o6_w7_directory_path_without_trailing_slash(self):
        repo = self.repo_with_base()
        self.write(repo, "src/deep/n.py", "# d\n")
        self.assertEqual(self.found(["src"]), [("src/deep/n.py", 1, "# d")])

    def test_o6_w8_file_path_matches_only_that_file(self):
        repo = self.repo_with_base()
        self.write(repo, "src/a.py", "x = 1\n# old\n# c\n")
        self.write(repo, "src/b.py", "y = 1\n# other\n")
        self.assertEqual(self.found(["src/a.py"]), [("src/a.py", 3, "# c")])

    def test_o6_w9_repository_without_commit_counts_every_line_as_added(self):
        repo = self.make_repo()
        self.write(repo, ".gitignore", "src/skip.py\n")
        self.write(repo, "src/a.py", "# c1\nx = 1\n# c2\n")
        self.write(repo, "src/skip.py", "# e\n")
        self.write(repo, "src/b.py", "# c3\n")
        git(repo, "add", "src/b.py")
        self.write(repo, "out/o.py", "# f\n")
        os.chdir(repo)
        self.assertEqual(
            self.found(["src/"]),
            [("src/a.py", 1, "# c1"), ("src/a.py", 3, "# c2"), ("src/b.py", 1, "# c3")],
        )

    def test_o6_c18_mixed_languages_with_real_scanner(self):
        repo = self.repo_with_base()
        self.write(repo, ".gitignore", "src/i.ts\n")
        self.write(repo, "src/a.py", "x = 1\n# old\n# c\n")
        self.write(repo, "src/n.ts", "// d\n")
        self.write(repo, "src/i.ts", "// e\n")
        self.write(repo, "out/o.ts", "// f\n")
        self.assertEqual(self.found(["src/"]), [("src/a.py", 3, "# c"), ("src/n.ts", 1, "// d")])


class ErrorTests(RepoTestCase):
    def test_o6_error_outside_a_repository_raises_comment_scan_error(self):
        module = load_module()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(tmp.name)
        self.assertTrue(issubclass(module.CommentScanError, Exception))
        with self.assertRaises(module.CommentScanError):
            module.working_tree_comments(["src/"])

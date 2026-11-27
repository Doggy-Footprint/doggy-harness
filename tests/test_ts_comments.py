from tests.test_comment_detection import DetectionCase, lines


class LexicalContextTests(DetectionCase):
    def test_o1_p1_line_comment(self):
        self.only("a.ts", lines("const a = 1;", "// note"), 2)

    def test_o1_p2_double_quoted_string_with_slashes(self):
        self.only("a.ts", lines('const u = "http://x/a // b";'))
        self.only("b.ts", lines('const u = "http://x/a // b";', "// after"), 2)

    def test_o1_p3_single_quoted_string_with_block_opener(self):
        self.only("a.ts", lines("const s = 'a /* b';", "const t = 1;"))
        self.only("b.ts", lines("const s = 'a /* b';", "// after"), 2)

    def test_o1_p4_template_text_with_slashes_and_hash_and_substitution_comment(self):
        self.only("a.ts", lines("const t = `line // x", "# y ${a /* c */}", "more`;"), 2)

    def test_o1_p4_template_text_alone_reports_nothing(self):
        self.only("a.ts", lines("const t = `line // x", "# y", "/* z */", "more`;"))

    def test_o1_p5_comment_in_template_substitution(self):
        self.only("a.ts", lines("const t = `v ${a /* c */} w`;"), 1)
        self.only("b.ts", lines("const t = `x ${", "  a // c", "}`;"), 2)

    def test_o1_p6_regex_literal_with_escaped_slashes(self):
        self.only("a.ts", lines(r"const r = /\/\/x/g;"))

    def test_o1_p7_division_next_to_regex(self):
        self.only("a.ts", lines("const d = a / b; const r = /x/g; const e = d / 2;"))
        self.only("b.ts", lines(r"const r = /\/\/x/g; const d = a / b;"))
        self.only("c.ts", lines("const d = a / b / c;", "const r = /x/g; // k"), 2)

    def test_o1_p8_jsx_attribute_string_with_slashes(self):
        self.only("a.tsx", lines('const e = <p title="// t">x</p>;'))

    def test_o1_p9_jsx_text_with_apostrophe_and_slashes(self):
        self.only("a.tsx", lines("const e = <p>Don't // x</p>;"))

    def test_o1_p10_comment_in_jsx_expression_container(self):
        self.only("a.tsx", lines('const e = <p title="// t">Don\'t // x {/* y */}</p>;', "// z"), 1, 2)

    def test_o1_p11_multi_line_block_comment_reports_every_line(self):
        self.only("a.ts", lines("const a = 1;", "/*", " * x", " */", "const b = 2;"), 2, 3, 4)

    def test_o1_p12_jsdoc_reports_every_line(self):
        self.only("a.ts", lines("/**", " * @param x", " */", "function f(x) {}"), 1, 2, 3)

    def test_o1_p13_private_field_is_not_a_comment(self):
        self.only("a.ts", lines("class A { #count = 0 }"))
        self.only("b.ts", lines("class B {", "  #count = 0;", "  get c() { return this.#count; }", "}"))


class ExtensionTests(DetectionCase):
    def test_o2_ts_family_parses_generic_arrow_then_reports_comment(self):
        for item, name in (("e1", "a.ts"), ("e2", "a.mts"), ("e3", "a.cts")):
            with self.subTest(item=item, name=name):
                self.only(name, lines("const f = <T,>(x: T) => x;", "// k"), 2)
                self.only("p" + name, lines("// k"), 1)

    def test_o2_tsx_and_js_family_parse_jsx_and_report_comments(self):
        for item, name in (("e4", "a.tsx"), ("e5", "a.js"), ("e6", "a.jsx"), ("e7", "a.mjs"), ("e8", "a.cjs")):
            with self.subTest(item=item, name=name):
                self.only(name, lines("const e = <p>{/* y */}</p>;", "// k"), 1, 2)
                self.only("p" + name, lines("// k"), 1)


class DirectiveTests(DetectionCase):
    DIRECTIVES = (
        ("d1", "a.ts", "// @ts-expect-error"),
        ("d1", "b.ts", "/* @ts-ignore */"),
        ("d1", "c.ts", "//@ts-nocheck"),
        ("d2", "a.ts", "/* eslint-disable */"),
        ("d2", "b.ts", "//   eslint-disable-next-line no-console"),
        ("d3", "a.ts", "// eslint-enable no-console"),
        ("d4", "a.ts", "// prettier-ignore"),
        ("d5", "a.ts", "// biome-ignore lint/style: reason"),
        ("d6", "a.ts", "/* istanbul ignore next */"),
        ("d7", "a.ts", "// c8 ignore next"),
        ("d8", "a.ts", "/* v8 ignore start */"),
        ("d9", "a.ts", "const x = /*#__PURE__*/ f();"),
        ("d10", "a.ts", "const x = /* @__PURE__ */ f();"),
        ("d11", "a.ts", 'const m = import(/* webpackChunkName: "x" */ "./m");'),
        ("d12", "a.ts", '/// <reference types="x" />'),
    )

    def test_o3_d1_to_d12_directives_are_not_reported(self):
        for item, name, text in self.DIRECTIVES:
            with self.subTest(item=item, name=name, text=text):
                self.only(item + name, lines("const a = 1;", text))

    def test_o3_d13_shebang_on_line_one_is_not_reported(self):
        self.only("a.js", lines("#!/usr/bin/env node", "let x = 1;"))

    def test_o3_d14_plain_comment_is_reported_as_control(self):
        self.only("a.ts", lines("const a = 1;", "// note"), 2)
        self.only("b.js", lines("let a = 1;", "// note"), 2)

    def test_o3_d12_triple_slash_without_reference_is_reported(self):
        self.only("a.ts", lines("const a = 1;", "/// plain note"), 2)
        self.only("b.ts", lines("const a = 1;", "/// <summary>"), 2)

    def test_o3_d2_multi_line_block_comment_starting_with_directive_reports_no_line(self):
        self.only("a.ts", lines("const a = 1;", "/* eslint-disable", "   no-console */", "const b = 2;"))

    def test_o3_d14_directive_text_not_at_comment_start_is_reported(self):
        self.only("a.ts", lines("// see @ts-ignore docs"), 1)


class RegressionTests(DetectionCase):
    def test_o5_n2_python_comment_docstring_and_trailing_comment(self):
        text = lines("x = 1", "# c", "def f():", '    """doc', '    more"""', "    return 1", "y = 2  # t")
        self.only("a.py", text, 2, 4, 5, 7)

    def test_o5_n3_kotlin_reports_every_line_of_a_kdoc_comment(self):
        self.only("a.kt", lines("val a = 1", "// c", "/**", " * k", " */", "fun f() {}"), 2, 3, 4, 5)

    def test_o5_n3_java_stays_on_the_line_pattern_and_reports_only_openers(self):
        self.only("a.java", lines("int a = 1;", "// c", "/**", " * k", " */", "int b;"), 2, 3)

    def test_o5_n4_yaml_hash_at_line_start_only(self):
        self.only("a.yaml", lines("a: 1", "# c", "b: 2 # t"), 2)


class KotlinCase(DetectionCase):
    def staged_set(self, name, text, *line_numbers):
        got, _, r = self.staged_report({}, {name: text})
        self.assertEqual(got, {(name, n) for n in line_numbers}, r.stderr)
        self.assertNotIn("could not run", r.stderr)


class KotlinLexicalContextTests(KotlinCase):
    def test_o1_p1_line_comment(self):
        self.staged_set("a.kt", lines("val a = 1", "// note"), 2)

    def test_o1_p2_trailing_comment(self):
        self.staged_set("a.kt", lines("fun f(s: String): String {", "    return s // trailing", "}"), 2)

    def test_o1_p3_kdoc_reports_every_line(self):
        self.staged_set("a.kt", lines("val a = 1", "/**", " * doc", " */", "fun f() {}"), 2, 3, 4)

    def test_o1_p4_block_comment_middle_line_without_star_is_reported(self):
        self.staged_set("a.kt", lines("val a = 1", "/*", "   body", " */", "fun f() {}"), 2, 3, 4)

    def test_o1_p5_nested_block_comment_is_one_comment(self):
        self.staged_set("a.kt", lines("/* a /* b */ still */", "val x = 1"), 1)

    def test_o1_p5_nested_multi_line_block_comment_reports_every_line(self):
        self.staged_set("a.kt", lines("/* a", "/* b */", "still */", "val x = 1"), 1, 2, 3)

    def test_o1_p6_string_with_slashes_and_block_opener_is_not_a_comment(self):
        self.staged_set("a.kt", lines('val u = "http://x // y /* z"', "val k = 1"))
        self.staged_set("b.kt", lines('val u = "http://x // y /* z"', "// after"), 2)

    def test_o1_p7_raw_string_inner_lines_are_not_comments(self):
        self.staged_set("a.kt", lines('val r = """', "// not", "# nope", '"""'))
        self.staged_set("b.kt", lines('val r = """', "// not", "# nope", '"""', "// after"), 5)

    def test_o1_p8_comment_in_string_template_substitution(self):
        self.staged_set("a.kt", lines('val t = "v ${x /* c */} $y"', "val k = 1"), 1)

    def test_o1_p9_comment_in_raw_string_template_substitution(self):
        self.staged_set("a.kt", lines('val r = """', "${ /* d */ x}", '"""'), 2)

    def test_o1_p8_p9_both_substitution_comments_in_one_file(self):
        text = lines('val t = "v ${x /* c */} $y"', 'val r = """', "${ /* d */ x}", '"""')
        self.staged_set("a.kt", text, 1, 3)

    def test_o1_p10_simple_template_reference_is_not_a_comment(self):
        self.staged_set("a.kt", lines('val s = "v $y w"', 'val t = "$y // z"', "// after"), 3)

    def test_o1_p11_annotation_division_and_char_slash_are_not_comments(self):
        self.staged_set("a.kt", lines('@Suppress("x")', "val d = a / b / c", "val ch = '/'"))
        self.staged_set("b.kt", lines('@Suppress("x")', "val d = a / b / c", "val ch = '/' // k"), 3)

    def test_o1_p12_shebang_on_line_one_of_main_kts_is_not_reported(self):
        self.staged_set("a.main.kts", lines("#!/usr/bin/env kotlin", "// k"), 2)

    def test_o1_p12_shebang_only_main_kts_reports_nothing(self):
        self.staged_set("a.main.kts", lines("#!/usr/bin/env kotlin", "val a = 1"))

    def test_o1_p13_kts_file_is_scanned(self):
        self.staged_set("build.gradle.kts", lines("plugins {}", "// k"), 2)

    def test_o1_p13_kts_block_comment_reports_every_line(self):
        self.staged_set("settings.kts", lines("/*", "   body", "*/"), 1, 2, 3)

    def test_o1_p14_locally_recovered_syntax_error_still_reports_the_comment(self):
        self.staged_set("a.kt", lines("val x = = 1", "// k"), 2)

    def test_o1_p15_unclosed_paren_swallowing_a_later_comment_scans_cleanly_and_reports_nothing(self):
        got, _, r = self.staged_report({}, {"a.kt": lines("val x = = (", "// k")})
        self.assertEqual(got, set(), r.stderr)
        self.assertEqual(r.returncode, 0)
        self.assertNotIn("could not run", r.stderr)
        self.assertNotIn("Traceback", r.stderr)


class KotlinDirectiveTests(KotlinCase):
    KOTLIN_DIRECTIVES = (
        ("d1", "a.kt", "// ktlint-disable"),
        ("d2", "b.kt", "/* ktlint-enable */"),
        ("d3", "c.kt", "//noinspection X"),
        ("d4", "d.kt", "// @formatter:off"),
        ("d5", "e.kt", "// @formatter:on"),
        ("d6", "f.kt", "// spotless:off"),
        ("d7", "g.kt", "// spotless:on"),
        ("d8", "h.kt", "// language=SQL"),
    )

    def test_o2_d1_to_d8_kotlin_directives_are_not_reported(self):
        for item, name, text in self.KOTLIN_DIRECTIVES:
            with self.subTest(item=item, text=text):
                self.staged_set(item + name, lines("val a = 1", text))

    def test_o2_kotlin_directives_in_one_file_report_nothing(self):
        self.staged_set("a.kt", lines(*[text for _, _, text in self.KOTLIN_DIRECTIVES]))

    def test_o2_directive_text_not_at_comment_start_is_reported(self):
        self.staged_set("a.kt", lines("// see ktlint-disable docs"), 1)

    def test_o2_d9_directive_after_a_second_line_comment_opener_is_reported(self):
        self.staged_set("a.kt", lines("// note // ktlint-disable", "// ktlint-disable"), 1)

    def test_o2_d9_directive_inside_a_nested_block_comment_is_reported(self):
        self.staged_set("a.kt", lines("/* note /* ktlint-disable */ */"), 1)

    def test_o2_d9_directive_in_a_second_comment_on_the_same_line_is_reported(self):
        self.staged_set("a.kt", lines("/* see */ // spotless:off"), 1)

    def test_o2_plain_comment_next_to_a_directive_is_reported(self):
        self.staged_set("a.kt", lines("// ktlint-disable", "// note"), 2)

    def test_o2_x1_kotlin_directive_in_ts_is_reported(self):
        self.staged_set("a.ts", lines("const a = 1;", "// ktlint-disable"), 2)

    def test_o2_x2_typescript_ts_ignore_in_kotlin_is_reported(self):
        self.staged_set("a.kt", lines("val a = 1", "// @ts-ignore"), 2)

    def test_o2_x3_eslint_disable_in_kotlin_is_reported(self):
        self.staged_set("a.kt", lines("val a = 1", "// eslint-disable"), 2)

    def test_o2_x1_x2_x3_together(self):
        got, _, r = self.staged_report(
            {},
            {"a.ts": lines("// ktlint-disable"), "b.kt": lines("// @ts-ignore", "// eslint-disable")},
        )
        self.assertEqual(got, {("a.ts", 1), ("b.kt", 1), ("b.kt", 2)}, r.stderr)

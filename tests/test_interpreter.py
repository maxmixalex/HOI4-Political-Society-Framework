"""Controls for the generated-script test harness, not a political-model mirror."""
import unittest

from hoi4_interpreter import Interpreter, ScriptError, entries, parse


class InterpreterControls(unittest.TestCase):
    def interpreter(self, text):
        result = Interpreter()
        result.effects = {node.key: node.value for node in entries(parse(text))}
        return result

    def test_executes_exactly_one_conditional_branch(self):
        vm = self.interpreter("""
        test = {
            set_variable = { value = 10 }
            if = {
                limit = { check_variable = { var = value value = 10 compare = equals } }
                add_to_variable = { value = 5 }
            }
            else_if = {
                limit = { always = yes }
                branch_that_must_not_execute = yes
            }
            else = { branch_that_must_not_execute = yes }
        }
        """)
        vm.run_effect("test")
        self.assertEqual(vm.state.variables["value"], 15)

    def test_unknown_effect_never_silently_passes(self):
        vm = self.interpreter("test = { unsupported_effect = yes }")
        with self.assertRaisesRegex(ScriptError, "Unsupported effect"):
            vm.run_effect("test")

    def test_actual_division_by_zero_is_an_error(self):
        vm = self.interpreter("test = { set_variable = { a = 1 } divide_variable = { a = 0 } }")
        with self.assertRaisesRegex(ScriptError, "Division by zero"):
            vm.run_effect("test")

    def test_temp_operands_survive_nested_effect_call(self):
        vm = self.interpreter("""
        outer = { set_temp_variable = { change = 7 } inner = yes }
        inner = { set_variable = { total = change } }
        """)
        vm.run_effect("outer")
        self.assertEqual(vm.state.variables["total"], 7)
        vm.run_effect("inner")
        self.assertEqual(vm.state.variables["total"], 0)

    def test_malformed_input_is_rejected(self):
        for text in ("test = {", "test = }", "test =", "test = { } }"):
            with self.subTest(text=text), self.assertRaises(ScriptError):
                parse(text)

    def test_country_modifier_operands_read_injected_engine_totals(self):
        vm = self.interpreter("""test = {
            set_variable = { observed = modifier@psf_test_support_daily }
            add_to_variable = { observed = ROOT.modifier@psf_test_influence_daily }
            set_variable = { missing = modifier@psf_inactive_source }
        }""")
        vm.state.modifier_values.update({"psf_test_support_daily": 0.25, "psf_test_influence_daily": -0.1})
        vm.run_effect("test")
        self.assertAlmostEqual(vm.state.variables["observed"], 0.15)
        self.assertEqual(vm.state.variables["missing"], 0)
        self.assertEqual(vm.state.undefined_reads, set())
        with self.assertRaisesRegex(ScriptError, "Invalid modifier reference"):
            vm.number("modifier@")

    def test_for_loop_matches_the_supplied_game_documentation_example(self):
        vm = self.interpreter("""test = {
            for_loop_effect = {
                start = -3 end = 10 add = 3 compare = less_than_or_equals value = i
                add_to_array = { values = i }
            }
        }""")
        vm.run_effect("test")
        self.assertEqual(vm.state.arrays["values"], [-3, 0, 3, 6, 9])
        self.assertNotIn("i", vm.state.variables)

    def test_for_loop_resizes_and_writes_the_real_chart_array_form(self):
        vm = self.interpreter("""test = {
            resize_array = { array = frames size = 6 value = 1 }
            for_loop_effect = {
                end = frames^num value = slice
                set_variable = { frames^slice = 1 }
            }
            set_temp_variable = { start = 2 }
            set_temp_variable = { end = 5 }
            for_loop_effect = {
                start = start end = end value = slice
                set_variable = { frames^slice = 4 }
            }
        }""")
        vm.state.arrays["frames"] = [99, 99, 99, 99, 99, 99, 99]
        vm.run_effect("test")
        self.assertEqual(vm.state.arrays["frames"], [1, 1, 4, 4, 4, 1])
        self.assertEqual(vm.number("frames^num"), 6)
        with self.assertRaisesRegex(ScriptError, "read-only"):
            vm.put("frames^num", 0)

    def test_resize_array_preserves_grows_truncates_and_clears(self):
        vm = self.interpreter("""
            grow = { resize_array = { array = values size = 4 value = 7 } }
            same = { resize_array = { values = 4 value = 90 } }
            shrink = { resize_array = { values = 1 } }
            clear = { resize_array = { values = 0 } }
            defaults = { resize_array = { values = 2 } }
        """)
        vm.state.arrays["values"] = [3, 4]
        vm.run_effect("grow")
        self.assertEqual(vm.state.arrays["values"], [3, 4, 7, 7])
        vm.run_effect("same")
        self.assertEqual(vm.state.arrays["values"], [3, 4, 7, 7])
        vm.run_effect("shrink")
        self.assertEqual(vm.state.arrays["values"], [3])
        vm.run_effect("clear")
        self.assertEqual(vm.state.arrays["values"], [])
        vm.run_effect("defaults")
        self.assertEqual(vm.state.arrays["values"], [0, 0])

    def test_for_loop_supports_break_and_descending_bounds(self):
        vm = self.interpreter("""test = {
            for_loop_effect = {
                start = 5 end = 0 add = -1 compare = greater_than_or_equals
                break = stop_here
                add_to_array = { values = v }
                if = {
                    limit = { check_variable = { v = 3 } }
                    set_temp_variable = { stop_here = 1 }
                }
            }
        }""")
        vm.run_effect("test")
        self.assertEqual(vm.state.arrays["values"], [5, 4, 3])

    def test_nested_loops_keep_distinct_counter_variables(self):
        vm = self.interpreter("""test = {
            for_loop_effect = {
                end = 2 value = outer
                for_loop_effect = {
                    end = 2 value = inner
                    set_temp_variable = { number = outer }
                    multiply_temp_variable = { number = 10 }
                    add_to_temp_variable = { number = inner }
                    add_to_array = { values = number }
                }
            }
        }""")
        vm.run_effect("test")
        self.assertEqual(vm.state.arrays["values"], [0, 1, 10, 11])

    def test_empty_unbounded_loop_is_an_error_not_a_success(self):
        vm = self.interpreter("test = { for_loop_effect = { end = 1 add = 0 } }")
        vm.max_loop_iterations = 3
        with self.assertRaisesRegex(ScriptError, "MAX_EFFECT_ITERATION"):
            vm.run_effect("test")

    def test_unsupported_loop_and_resize_forms_are_rejected(self):
        for effect in (
            "for_loop_effect = yes", "for_loop_effect = { end = 2 compare = maybe }",
            "for_loop_effect = { end = 2 end = 3 }", "while_loop_effect = { limit = { always = yes } }",
            "resize_array = { array = values }", "resize_array = { values = -1 }",
            "resize_array = { values = 1.5 }", "resize_array = { values = 2 unexpected = 4 }",
            "resize_array = { array = values size = 2 size = 3 }",
        ):
            with self.subTest(effect=effect), self.assertRaises(ScriptError):
                self.interpreter(f"test = {{ {effect} }}").run_effect("test")

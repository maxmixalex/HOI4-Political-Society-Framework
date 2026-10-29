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

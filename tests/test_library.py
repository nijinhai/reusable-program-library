import tempfile
import unittest
from pathlib import Path
from program_library.synthesis import Learned, propose
from program_library.runtime import search, score
from program_library.support import freeze, verify


class LibraryTests(unittest.TestCase):
    def test_reverse_generalizes_to_unseen_input(self):
        fn, fees = propose(
            [{"input": "abc-Def", "output": "feD-cba"}, {"input": "XyZ-wvu", "output": "uvw-ZyX"}],
            [{"input": "ijk-LmN", "output": "NmL-kji"}])
        self.assertIsNotNone(fn)
        self.assertEqual(fn.apply("opq-RsT"), "TsR-qpo")
        self.assertGreater(fees["calls"], 0)

    def test_affine_parameters_are_fitted(self):
        fit = [{"input": f"n={n}", "output": str(2*n+3)} for n in (101,227,349,463)]
        fn, _ = propose(fit, [{"input": "n=577", "output": "1157"}])
        self.assertIsNotNone(fn)
        self.assertEqual(fn.apply("n=691"), "1385")

    def test_validation_can_reject_fitted_hypotheses(self):
        fn, _ = propose([{"input": "abc", "output": "cba"}, {"input": "def", "output": "fed"}],
                        [{"input": "ghi", "output": "impossible-12345"}])
        self.assertIsNone(fn)

    def test_acquired_function_composes_after_existing_primitive(self):
        fn = Learned("text[::-1]", "reverse")
        bank = {fn.mid: fn}
        result = search(["tag/abc-DeF", "other/ghi-JkL"], ["FeD-cba", "LkJ-ihg"], bank)
        self.assertTrue(result["exact_fit"])
        mask, _ = score(result["program"], [{"input": "new/mno-PqR", "output": "RqP-onm"}], bank)
        self.assertTrue(all(mask))
        self.assertTrue(any("learned" in t for t in result["program"]))
        self.assertTrue(any("base" in t for t in result["program"]))

    def test_insufficient_budget_does_not_return_partial_learned_call(self):
        fn = Learned("text.replace('_',':').upper()", "replace")
        result = search(["a_b"], ["A:B"], {fn.mid: fn}, budget=1)
        self.assertFalse(result["exact_fit"])
        self.assertEqual(result["learned_calls"], 0)

    def test_frozen_tasks_detect_mutation_and_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            freeze(out, "test", [], [{"input": "a"}])
            verify(out)
            with self.assertRaises(RuntimeError):
                freeze(out, "test", [], [])
            (out / "tasks_frozen.json").write_text("[]")
            with self.assertRaises(RuntimeError):
                verify(out)


if __name__ == "__main__":
    unittest.main()

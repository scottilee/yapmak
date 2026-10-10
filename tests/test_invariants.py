"""IR-parameterized invariants on the fixtures and on a small seeded set of generated policy permutations."""
import json
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
import invariants as I  # noqa: E402
import permute_policies as PP  # noqa: E402
import policy as P  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
API = str(ROOT / "tools/openapi.json")


def _failing(rep):
    return [s for s, p in rep.get("scenarios", {}).items() if p and not p[0].startswith("n/a")]


def test_fixture_a_satisfies_invariants():
    rep = I.check_policy(str(ROOT / "tests/fixtures/brief_a.policy.json"), API, verbose=False)
    assert not rep.get("invalid") and not rep.get("static") and not _failing(rep), rep


def test_fixture_ab_satisfies_invariants():
    rep = I.check_policy(str(ROOT / "tests/fixtures/brief_a.policy.json") + "+" + str(ROOT / "tests/fixtures/brief_ab.policy.json"), API, verbose=False)
    assert not rep.get("invalid") and not rep.get("static") and not _failing(rep), rep
    assert not rep["scenarios"]["dispute_one"], "two products: dispute on one, promise on the other"


def test_generated_permutations_satisfy_invariants(tmp_path):
    base = json.load(open(ROOT / "tests/fixtures/brief_a.policy.json"))
    base = P.merge_overlay(base, json.load(open(ROOT / "tests/fixtures/brief_ab.policy.json")))
    api = json.load(open(API))
    rng = random.Random(11)
    bad = []
    for k in range(6):
        ir, v = PP.permute(base, rng, k)
        spec = PP.mutate_openapi(api, ir, v)
        pp, op = tmp_path / f"p{k}.policy.json", tmp_path / f"p{k}.openapi.json"
        pp.write_text(json.dumps(ir)); op.write_text(json.dumps(spec))
        rep = I.check_policy(str(pp), str(op), verbose=False)
        if rep.get("invalid") or rep.get("static") or _failing(rep):
            bad.append((k, rep.get("invalid"), rep.get("static"), {s: rep["scenarios"][s] for s in _failing(rep)}))
    assert not bad, bad

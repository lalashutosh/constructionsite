import pytest

from contracts import invariants
from contracts.proof import Element, Provenance, SheetFacts, Tag, Tier, Voter
from engine import cache as facts_cache
from engine import pipeline as P
from engine import registry as R
from engine.query.llm import LLMReply

WIN_Q = "How many windows are shown on this floor plan?"
PATH = "data/cubicasa5k/a.png"


def _sq(i, kind="window", x=0):
    return Element(id=f"{kind}{i}", kind=kind, polygon=[(x, 0), (x + 5, 0), (x + 5, 5), (x, 5)])


@pytest.fixture
def env(tmp_path, monkeypatch):
    (tmp_path / "data" / "cubicasa5k").mkdir(parents=True)
    (tmp_path / PATH).write_bytes(b"not really a png")
    monkeypatch.setenv("DATASET_ROOT", str(tmp_path))
    monkeypatch.setattr(facts_cache, "CACHE_DIR", tmp_path / "cache")
    facts_cache.clear_memory()
    R.reset()
    P._DISCOVERED = True  # keep the registry exactly as the test sets it

    def make(facts=None, llm=None):
        f = facts or SheetFacts(provenance=Provenance(file=PATH, fmt="png"), sheet_type="floor_plan",
                                elements=[_sq(i, x=20 * i) for i in range(3)])
        monkeypatch.setattr(P.PipelineEngine, "_extract", lambda self, *a, **k: f.model_copy(deep=True))
        eng = P.PipelineEngine(llm=llm)
        eng._prior = {"intent": {}, "source_type": {}, "type": {}}
        return eng
    yield make
    R.reset()
    P._DISCOVERED = False


def _voter(name, value, note=None, runs=None, exact=False):
    return lambda ctx: R.VoterResult(Voter(name=name, value=value, runs=runs or [value], note=note), exact=exact)


def test_zero_plugins_amber_with_note(env):
    po = env().ask(PATH, WIN_Q)
    assert po.tier == Tier.amber and po.value == 0
    assert any("no voter" in n for n in po.notes)
    assert invariants.check(po) == []


def test_raising_voter_is_a_note(env):
    def boom(ctx):
        raise RuntimeError("kaput")
    R.register_voter("boom", boom)
    R.register_voter("ok", _voter("ok", 3))
    po = env().ask(PATH, WIN_Q)
    assert po.value == 3 and any("boom failed" in n for n in po.notes)


def test_disagreement_is_amber(env):
    R.register_voter("a", _voter("a", 3))
    R.register_voter("b", _voter("b", 4))
    po = env().ask(PATH, WIN_Q)
    assert po.tier == Tier.amber and po.value in (3, 4)


def test_two_agreeing_voters_green(env):
    R.register_voter("a", _voter("a", 3))
    R.register_voter("b", _voter("b", 3))
    po = env().ask(PATH, WIN_Q)
    assert po.tier == Tier.green and po.value == 3 and invariants.check(po) == []


def test_exact_voter_wins(env):
    R.register_voter("a", _voter("a", 3))
    R.register_voter("b", _voter("dxf", 5, exact=True))
    assert env().ask(PATH, WIN_Q).value == 5


def test_count_defaults_tag_defaulted_and_not_green(env):
    facts = SheetFacts(provenance=Provenance(file=PATH, fmt="png"), sheet_type="floor_plan",
                       extras={"count_defaults": {"windows": {"value": 1, "reason": "dev-median prior"}}})
    R.register_voter("det", _voter("detector", 1, note="prior fallback, no detector evidence"))
    R.register_voter("b", _voter("skeptic", 1))
    po = env(facts).ask(PATH, WIN_Q)
    a = [x for x in po.assumptions if x.key == "count:windows"]
    assert a and a[0].tag == Tag.defaulted and a[0].source == "dev-median prior"
    assert po.tier == Tier.amber  # the prior voter does not count toward agreement


def test_triage_refuses_in_product_mode_only(env):
    R.register_triage("t", lambda ctx: R.TriageResult(sheet_type="elevation", refuse="this is an elevation"))
    R.register_voter("a", _voter("a", 3))
    eng = env()
    grey = eng.ask(PATH, WIN_Q, benchmark=False)
    assert grey.tier == Tier.grey and grey.value is None and grey.refusal and invariants.check(grey) == []
    bench = eng.ask(PATH, WIN_Q, benchmark=True)
    assert bench.value == 3 and bench.tier != Tier.green


def test_facts_cached_once_per_sha(env, monkeypatch):
    eng = env()
    n = {"c": 0}
    orig = P.PipelineEngine._extract

    def counting(self, *a, **k):
        n["c"] += 1
        return orig(self, *a, **k)
    monkeypatch.setattr(P.PipelineEngine, "_extract", counting)
    eng.ask(PATH, WIN_Q)
    eng.ask(PATH, "How many doors are shown on this floor plan?")
    assert n["c"] == 1
    eng.ask(PATH, WIN_Q, allow_siblings=False)  # different cache key
    assert n["c"] == 2


class FakeLLM:
    def __init__(self, text):
        self.text, self.calls = text, 0

    def complete(self, system, user, max_tokens=400):
        self.calls += 1
        return LLMReply(self.text, 100, 20, 0.001)


def test_planner_fake_llm_sets_spec_and_never_takes_number(env):
    llm = FakeLLM('The answer is 99. {"select": "window", "aggregate": "count"}')
    po = env(llm=llm).ask(PATH, "zzqq vvxx wwkk jjhh")
    assert po.value == 3                      # computed by code from elements, not the LLM's 99
    assert po.query_spec == {"select": "window", "aggregate": "count"}
    assert po.cost.planner_calls == 1 and po.cost.llm_calls >= 1
    assert po.tier == Tier.amber and invariants.check(po) == []


def test_planner_rejects_bad_spec(env):
    llm = FakeLLM('{"select": "window", "aggregate": "count", "value": 99}')
    po = env(llm=llm).ask(PATH, "zzqq vvxx wwkk jjhh")
    assert po.query_spec is None and po.cost.planner_calls == 0 and po.cost.llm_calls >= 1
    assert po.value != 99 and any("planner failed" in n for n in po.notes)
    assert invariants.check(po) == []


def test_llm_template_calls_le_distinct_templates(env, tmp_path):
    from engine.router import TemplateClassifier, route
    llm = FakeLLM("windows")
    clf = TemplateClassifier(llm, cache_path=tmp_path / "templates.json")
    templates = ["zzqq vvxx wwkk %d", "mmnn ppoo rrss %d", "bbcc ddff gghh %d"]
    for i in range(30):
        r = route(templates[i % 3] % i, PATH, classifier=clf)
        assert r.intent == "windows" and r.layer == "llm"
    assert llm.calls == clf.calls <= 3
    # a fresh classifier reads the on-disk cache: zero extra calls
    clf2 = TemplateClassifier(llm, cache_path=tmp_path / "templates.json")
    route(templates[0] % 77, PATH, classifier=clf2)
    assert llm.calls == 3


def test_user_verdict_corrects_voters_and_recomputes_tier():
    """Skeptic Duel: voter A sees 2 doors, voter B sees 1; the user confirms the door only A saw ->
    B gains it, both say 2, tier is recomputed from agreement (green), verdict recorded as `chosen`."""
    from contracts.proof import Element, ProofObject, Provenance, Tag, Voter
    from engine import registry
    from engine.pipeline import PipelineEngine, compute_tier

    sq = lambda x: [(x, 0.0), (x + 1, 0.0), (x + 1, 1.0), (x, 1.0)]
    a = registry.VoterResult(voter=Voter(name="detector", value=2), evidence=[
        Element(id="a1", kind="door", polygon=sq(0)), Element(id="a2", kind="door", polygon=sq(5))])
    b = registry.VoterResult(voter=Voter(name="doors_arc", value=1), evidence=[
        Element(id="b1", kind="door", polygon=sq(0))], second_opinion=True)
    eng = PipelineEngine.__new__(PipelineEngine)
    eng.overrides = {("sha", "doors"): [{"id": "a2", "polygon": sq(5), "keep": True}]}
    po = ProofObject(id="x", question="q", provenance=Provenance(file="f"))
    eng._apply_overrides([a, b], "sha", "doors", po, po.notes)
    assert (a.voter.value, b.voter.value) == (2, 2)
    assert compute_tier([a, b], "count")[0].value == "green"
    assert po.assumptions and po.assumptions[0].tag == Tag.chosen

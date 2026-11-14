from engine import registry as R
from contracts.proof import Voter


def test_register_and_lookup():
    R.reset()
    R.register_voter("a", lambda ctx: R.VoterResult(Voter(name="a", value=3)), kinds=("count",))
    R.register_voter("b", lambda ctx: None, kinds=("area",))
    assert [n for n, _ in R.voters_for("count")] == ["a"]
    assert [n for n, _ in R.voters_for("area")] == ["b"]
    ctx = R.Ctx(path="p", abs_path="/x/p", question="q", intent="doors")
    assert R.voters_for("count")[0][1](ctx).voter.value == 3


def test_resolver_priority_order():
    R.reset()
    R.register_resolver("late", lambda p, a: None, priority=90)
    R.register_resolver("early", lambda p, a: R.Resolved(p, "ifc"), priority=10)
    assert [n for n, _ in R.resolvers()] == ["early", "late"]


def test_autodiscover_skips_missing_modules():
    R.reset()
    loaded = R.autodiscover(extra=("engine.does_not_exist.plugin",))
    assert isinstance(loaded, list)

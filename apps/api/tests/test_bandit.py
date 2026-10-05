import numpy as np

from app.eval import bandit


# Arm 0 is right on short questions, arm 1 on long ones. Only features can tell them apart.
def make_rounds(n: int, seed: int) -> list[bandit.Round]:
    rng = np.random.default_rng(seed)
    rounds = []
    for i in range(n):
        long = bool(rng.integers(2))
        x = np.array([1.0, 1.0 if long else 0.0])
        rounds.append(bandit.Round(qid=i, x=x, correct=(not long, long), cost=(0.0, 0.0)))
    return rounds


def test_linucb_learns_context_and_ucb_cannot() -> None:
    train, test = make_rounds(60, 0), make_rounds(200, 1)
    linucb = bandit.train(train, lam=0.0, alpha=0.5, seed=0, epochs=3)
    ucb = bandit.train(train, lam=0.0, alpha=0.5, seed=0, epochs=3, contextual=False)
    lin_acc, _ = bandit.evaluate(bandit.greedy_choices(linucb, test, True, 0), test)
    ucb_acc, _ = bandit.evaluate(bandit.greedy_choices(ucb, test, False, 0), test)
    assert lin_acc == 1.0
    assert ucb_acc < 0.7


def test_cost_penalty_moves_choice_to_cheap_arm() -> None:
    x = np.array([1.0])
    rounds = [bandit.Round(i, x, correct=(True, True), cost=(0.0, 0.01)) for i in range(30)]
    policy = bandit.train(rounds, lam=100.0, alpha=0.5, seed=0, epochs=2)
    assert bandit.greedy_choices(policy, rounds[:5], True, 0) == [0] * 5

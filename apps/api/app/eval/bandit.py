"""Contextual bandit router: LinUCB over cheap question features.

Each question is one round. The policy sees the question's features, picks one arm, and
only learns that arm's reward: 1 if correct, minus lam * cost in USD. lam is the price
trade-off: lam = 100 means one extra correct answer is worth paying $0.01 for.
"""

import re
from dataclasses import dataclass

import numpy as np

TEMPORAL = re.compile(
    r"\b(before|after|when|year|as of|first|last|since|until|during|older|younger|born|died)\b",
    re.IGNORECASE,
)
NUMERIC = re.compile(
    r"\b(how many|how much|how old|difference|total|sum|average|percent)\b", re.IGNORECASE
)


def features(question: str) -> np.ndarray:
    """Bias plus six rough signals of how hard and multi-hop a question is, scaled near [0, 1]."""
    words = question.split()
    capitalized = sum(1 for w in words[1:] if w[:1].isupper())
    return np.array(
        [
            1.0,
            min(len(words) / 80, 1.5),
            min(capitalized / 15, 1.5),
            min(len(re.findall(r"\d+", question)) / 5, 1.5),
            min(len(TEMPORAL.findall(question)) / 4, 1.5),
            1.0 if NUMERIC.search(question) else 0.0,
            min((question.count(",") + question.count(" and ")) / 6, 1.5),
        ]
    )


# What every arm did on one question. Full outcomes exist only because the eval ran every
# arm; the bandit itself is shown just the arm it picked.
@dataclass(frozen=True)
class Round:
    qid: int
    x: np.ndarray
    correct: tuple[bool, ...]
    cost: tuple[float, ...]

    def reward(self, arm: int, lam: float) -> float:
        return float(self.correct[arm]) - lam * self.cost[arm]


class LinUCB:
    """Disjoint LinUCB (Li et al. 2010): one ridge regression per arm plus an optimism bonus."""

    def __init__(self, n_arms: int, dim: int, alpha: float, reg: float = 1.0) -> None:
        self.alpha = alpha
        self.A = np.stack([np.eye(dim) * reg for _ in range(n_arms)])
        self.b = np.zeros((n_arms, dim))

    def scores(self, x: np.ndarray, explore: bool) -> np.ndarray:
        A_inv = np.linalg.inv(self.A)
        theta = np.einsum("aij,aj->ai", A_inv, self.b)
        mean = theta @ x
        if not explore:
            return mean
        width = np.sqrt(np.einsum("i,aij,j->a", x, A_inv, x))
        return mean + self.alpha * width

    def choose(self, x: np.ndarray, rng: np.random.Generator, explore: bool = True) -> int:
        s = self.scores(x, explore)
        return int(rng.choice(np.flatnonzero(s >= s.max() - 1e-12)))

    def update(self, arm: int, x: np.ndarray, reward: float) -> None:
        self.A[arm] += np.outer(x, x)
        self.b[arm] += reward * x


def train(
    rounds: list[Round], lam: float, alpha: float, seed: int, epochs: int, contextual: bool = True
) -> LinUCB:
    """Replays the training questions in shuffled passes with bandit feedback only.

    contextual=False drops the features (x = [1]), which turns LinUCB into plain UCB.
    """
    rng = np.random.default_rng(seed)
    n_arms = len(rounds[0].correct)
    dim = len(rounds[0].x) if contextual else 1
    policy = LinUCB(n_arms, dim, alpha)
    for _ in range(epochs):
        for i in rng.permutation(len(rounds)):
            r = rounds[i]
            x = r.x if contextual else np.ones(1)
            arm = policy.choose(x, rng)
            policy.update(arm, x, r.reward(arm, lam))
    return policy


def evaluate(choices: list[int], rounds: list[Round]) -> tuple[float, float]:
    """Accuracy and mean USD cost of picking choices[i] on rounds[i]."""
    accuracy = float(np.mean([r.correct[a] for a, r in zip(choices, rounds, strict=True)]))
    cost = float(np.mean([r.cost[a] for a, r in zip(choices, rounds, strict=True)]))
    return accuracy, cost


def greedy_choices(policy: LinUCB, rounds: list[Round], contextual: bool, seed: int) -> list[int]:
    rng = np.random.default_rng(seed)
    return [policy.choose(r.x if contextual else np.ones(1), rng, explore=False) for r in rounds]

"""Anchored k-means.

Existing styles act as *fixed* centroids ("anchors"): a point may join an
anchor but anchors never move. On top of those, k *free* centroids are fitted
with ordinary Lloyd iterations. The smallest k for which every point sits
acceptably close to its centroid is chosen, so free clusters only appear when
manual formatting cannot be explained by existing styles - and any free
cluster with several members is a candidate for a new style.

Pure Python, no numpy: documents rarely have more than a few hundred
candidates.
"""
import math
import random


def dist(x, y):
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(x, y)))


def mean(vectors):
    n = len(vectors)
    return [sum(col) / n for col in zip(*vectors)]


class Fit:
    """labels[i] is ("anchor", anchor_id), ("free", j) or None (nowhere to go)."""

    def __init__(self, labels, centroids, inertia):
        self.labels, self.centroids, self.inertia = labels, centroids, inertia

    @property
    def k(self):
        return len(self.centroids)

    def members(self, label):
        return [i for i, l in enumerate(self.labels) if l == label]


def _nearest_anchor(x, anchors):
    best = (math.inf, None)
    for aid, vec in anchors:
        d = dist(x, vec)
        if d < best[0]:
            best = (d, aid)
    return best


def _seed(points, anchors, k, rng):
    """k-means++ seeding where existing anchors count as already-chosen
    centres, so seeds favour points no style explains."""
    centres = []
    for _ in range(k):
        d2 = []
        for i, x in enumerate(points):
            d = _nearest_anchor(x, anchors[i])[0]
            for c in centres:
                d = min(d, dist(x, c))
            d2.append(d * d)
        finite = [v for v in d2 if v != math.inf]
        big = (max(finite) if finite else 1.0) * 4 + 1.0
        weights = [big if v == math.inf else v for v in d2]
        total = sum(weights)
        if total <= 0:
            centres.append(list(points[rng.randrange(len(points))]))
            continue
        r, acc = rng.random() * total, 0.0
        for i, w in enumerate(weights):
            acc += w
            if acc >= r:
                centres.append(list(points[i]))
                break
        else:
            centres.append(list(points[-1]))
    return centres


def _assign(points, anchors, centres):
    labels, dists = [], []
    for i, x in enumerate(points):
        d, aid = _nearest_anchor(x, anchors[i])
        label = ("anchor", aid) if aid is not None else None
        for j, c in enumerate(centres):
            dc = dist(x, c)
            if dc < d - 1e-12:  # ties go to the existing style
                d, label = dc, ("free", j)
        labels.append(label)
        dists.append(d)
    return labels, dists


def run(points, anchors, k, rng, max_iter=100):
    centres = _seed(points, anchors, k, rng) if k else []
    labels = None
    for _ in range(max_iter):
        new_labels, dists = _assign(points, anchors, centres)
        if new_labels == labels:
            break
        labels = new_labels
        for j in range(k):
            members = [points[i] for i, l in enumerate(labels) if l == ("free", j)]
            if members:
                centres[j] = mean(members)
            else:  # empty cluster: restart it on the worst-served point
                worst = max(range(len(points)), key=lambda i: dists[i])
                centres[j] = list(points[worst])
    labels, dists = _assign(points, anchors, centres)
    inertia = sum(d * d for d in dists if d != math.inf) + 1e9 * dists.count(math.inf)
    return Fit(labels, centres, inertia)


def fit(points, anchors, accept, seed=0, n_init=8, k_max=None):
    """Fit with the smallest number of free centroids for which every point is
    acceptably close to its centroid (anchor or free).

    points  : list of vectors
    anchors : per point, list of (anchor_id, vector) the point may join
    accept  : accept(i, centroid_vector) -> bool
    """
    if not points:
        return Fit([], [], 0.0)
    distinct = len({tuple(round(v, 9) for v in p) for p in points})
    k_max = distinct if k_max is None else min(k_max, distinct)
    best = None
    for k in range(k_max + 1):
        rng = random.Random(seed + k)
        best = min((run(points, anchors, k, rng) for _ in range(n_init if k else 1)),
                   key=lambda f: f.inertia)
        if all(lab is not None and accept(i, centroid(best, anchors[i], lab))
               for i, lab in enumerate(best.labels)):
            return best
    return best


def centroid(fit_, point_anchors, label):
    if label[0] == "free":
        return fit_.centroids[label[1]]
    return next(vec for aid, vec in point_anchors if aid == label[1])

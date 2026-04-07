"""Inter-annotator agreement metrics (pure Python, no scipy/sklearn)."""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from typing import Any

from app.schemas.iaa import DimensionAgreement, IAAResponse


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


class IAAService:
    """Compute IAA metrics from normalized annotation rows."""

    EPS = 1e-12

    @staticmethod
    def normalize_annotation_rows(raw: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for row in raw:
            if not isinstance(row, dict):
                continue
            aid = row.get("annotator_id")
            tid = row.get("task_id")
            if aid is None or tid is None:
                continue
            if isinstance(aid, str):
                try:
                    aid = uuid.UUID(aid)
                except ValueError:
                    continue
            elif not isinstance(aid, uuid.UUID):
                continue
            pref = row.get("preference")
            pref_i: int | None = pref if isinstance(pref, int) else None
            dims_in = row.get("dimensions")
            dims: dict[str, int] = {}
            if isinstance(dims_in, dict):
                for k, v in dims_in.items():
                    if isinstance(k, str) and isinstance(v, int):
                        dims[k] = v
            out.append(
                {
                    "annotator_id": aid,
                    "task_id": str(tid),
                    "preference": pref_i,
                    "dimensions": dims,
                },
            )
        return out

    @staticmethod
    def _dedupe_per_task(
        annotations: list[dict[str, Any]],
        value_getter: Callable[[dict[str, Any]], int | None],
    ) -> dict[str, dict[uuid.UUID, int]]:
        """task_id -> {annotator_id: value} (last wins)."""
        acc: dict[str, dict[uuid.UUID, int]] = defaultdict(dict)
        for row in annotations:
            tid = row["task_id"]
            aid: uuid.UUID = row["annotator_id"]
            v = value_getter(row)
            if v is None:
                continue
            acc[tid][aid] = v
        return acc

    @staticmethod
    def _overlap_tasks(by_task: dict[str, dict[uuid.UUID, int]]) -> dict[str, dict[uuid.UUID, int]]:
        return {t: m for t, m in by_task.items() if len(m) >= 2}

    @staticmethod
    def cohens_kappa_two_raters(labels_a: list[int], labels_b: list[int]) -> float | None:
        """Paired nominal ratings (same length, aligned items)."""
        if len(labels_a) != len(labels_b) or not labels_a:
            return None
        n = len(labels_a)
        agree = sum(1 for x, y in zip(labels_a, labels_b, strict=True) if x == y)
        p_o = agree / n
        cats: set[int] = set(labels_a) | set(labels_b)
        p_e = 0.0
        for c in cats:
            pa = sum(1 for x in labels_a if x == c) / n
            pb = sum(1 for y in labels_b if y == c) / n
            p_e += pa * pb
        denom = 1.0 - p_e
        if denom <= IAAService.EPS:
            return 1.0 if abs(p_o - p_e) <= IAAService.EPS else None
        return (p_o - p_e) / denom

    @staticmethod
    def scotts_pi_two_raters(labels_a: list[int], labels_b: list[int]) -> float | None:
        """Scott's Pi for two raters (paired items)."""
        if len(labels_a) != len(labels_b) or not labels_a:
            return None
        n = len(labels_a)
        p_o = sum(1 for x, y in zip(labels_a, labels_b, strict=True) if x == y) / n
        cats: set[int] = set(labels_a) | set(labels_b)
        pi: dict[int, float] = {c: 0.0 for c in cats}
        for c in cats:
            cnt = sum(1 for x in labels_a if x == c) + sum(1 for y in labels_b if y == c)
            pi[c] = cnt / (2 * n)
        p_e = sum(p * p for p in pi.values())
        denom = 1.0 - p_e
        if denom <= IAAService.EPS:
            return 1.0 if abs(p_o - p_e) <= IAAService.EPS else None
        return (p_o - p_e) / denom

    @staticmethod
    def average_pairwise_cohens_kappa(overlap: dict[str, dict[uuid.UUID, int]]) -> float | None:
        annotators = sorted({a for m in overlap.values() for a in m})
        if len(annotators) < 2:
            return None
        kappas: list[float] = []
        for i in range(len(annotators)):
            for j in range(i + 1, len(annotators)):
                ai, aj = annotators[i], annotators[j]
                la: list[int] = []
                lb: list[int] = []
                for m in overlap.values():
                    if ai in m and aj in m:
                        la.append(m[ai])
                        lb.append(m[aj])
                k = IAAService.cohens_kappa_two_raters(la, lb)
                if k is not None:
                    kappas.append(k)
        if not kappas:
            return None
        return sum(kappas) / len(kappas)

    @staticmethod
    def scotts_pi(overlap: dict[str, dict[uuid.UUID, int]]) -> float | None:
        """Average pairwise Scott's Pi (multi-rater generalization)."""
        return IAAService.average_pairwise_scotts_pi(overlap)

    @staticmethod
    def average_pairwise_scotts_pi(overlap: dict[str, dict[uuid.UUID, int]]) -> float | None:
        annotators = sorted({a for m in overlap.values() for a in m})
        if len(annotators) < 2:
            return None
        pis: list[float] = []
        for i in range(len(annotators)):
            for j in range(i + 1, len(annotators)):
                ai, aj = annotators[i], annotators[j]
                la: list[int] = []
                lb: list[int] = []
                for m in overlap.values():
                    if ai in m and aj in m:
                        la.append(m[ai])
                        lb.append(m[aj])
                p = IAAService.scotts_pi_two_raters(la, lb)
                if p is not None:
                    pis.append(p)
        if not pis:
            return None
        return sum(pis) / len(pis)

    @staticmethod
    def fleiss_kappa(overlap: dict[str, dict[uuid.UUID, int]]) -> float | None:
        """Fleiss' kappa; requires the same number of raters on every included task."""
        if not overlap:
            return None
        sizes = {len(m) for m in overlap.values()}
        if len(sizes) != 1:
            return None
        n_raters = next(iter(sizes))
        if n_raters < 2:
            return None
        categories = sorted({v for m in overlap.values() for v in m.values()})
        if not categories:
            return None
        k = len(categories)
        idx = {c: i for i, c in enumerate(categories)}
        n_subjects = len(overlap)
        matrix: list[list[int]] = [[0] * k for _ in range(n_subjects)]
        for si, tid in enumerate(sorted(overlap.keys())):
            m = overlap[tid]
            for v in m.values():
                matrix[si][idx[v]] += 1
        for row in matrix:
            if sum(row) != n_raters:
                return None
        p_rows: list[float] = []
        for row in matrix:
            sum_sq = sum(x * x for x in row)
            p_rows.append((sum_sq - n_raters) / (n_raters * (n_raters - 1)))
        p_bar = sum(p_rows) / n_subjects
        p_j = [
            sum(matrix[i][j] for i in range(n_subjects)) / (n_subjects * n_raters) for j in range(k)
        ]
        p_bar_e = sum(p * p for p in p_j)
        denom = 1.0 - p_bar_e
        if denom <= IAAService.EPS:
            return 1.0 if abs(p_bar - p_bar_e) <= IAAService.EPS else None
        return (p_bar - p_bar_e) / denom

    @staticmethod
    def percentage_agreement_all_same(overlap: dict[str, dict[uuid.UUID, int]]) -> float:
        if not overlap:
            return 0.0
        agree = sum(1 for m in overlap.values() if len(set(m.values())) == 1)
        return agree / len(overlap)

    @staticmethod
    def _reliability_matrix(
        overlap: dict[str, dict[uuid.UUID, int]],
        annotators: list[uuid.UUID],
    ) -> tuple[list[list[int | None]], list[str]]:
        """Rows = tasks (pairable units), cols = annotators in fixed order."""
        task_ids = sorted(overlap.keys())
        aid_to_col = {a: j for j, a in enumerate(annotators)}
        rows: list[list[int | None]] = []
        for tid in task_ids:
            m = overlap[tid]
            row: list[int | None] = [None] * len(annotators)
            for aid, val in m.items():
                row[aid_to_col[aid]] = val
            rows.append(row)
        return rows, task_ids

    @staticmethod
    def krippendorff_alpha(
        overlap: dict[str, dict[uuid.UUID, int]],
        *,
        level: str,
    ) -> float | None:
        """
        Krippendorff's alpha via coincidence matrix (ordered coder pairs).
        `level` is 'nominal' or 'ordinal' (ordinal uses Wikipedia's delta_ordinal).
        """
        if not overlap:
            return None
        annotators = sorted({a for m in overlap.values() for a in m})
        rows, _task_ids = IAAService._reliability_matrix(overlap, annotators)
        pairable_rows = []
        for row in rows:
            vals = [v for v in row if v is not None]
            if len(vals) >= 2:
                pairable_rows.append(row)
        if not pairable_rows:
            return None

        n_total = sum(1 for row in pairable_rows for v in row if v is not None)
        if n_total < 2:
            return None
        n_minus_1 = n_total - 1
        if n_minus_1 <= IAAService.EPS:
            return None

        o: dict[int, dict[int, float]] = defaultdict(lambda: defaultdict(float))
        n_v: dict[int, float] = defaultdict(float)

        for row in pairable_rows:
            present = [(j, row[j]) for j in range(len(row)) if row[j] is not None]
            m_u = len(present)
            for ia in range(m_u):
                for ib in range(m_u):
                    if ia == ib:
                        continue
                    va = present[ia][1]
                    vb = present[ib][1]
                    if va is None or vb is None:
                        continue
                    o[va][vb] += 1.0 / (m_u - 1)

        for row in pairable_rows:
            for v in row:
                if v is not None:
                    n_v[int(v)] += 1.0

        values_sorted = sorted(n_v.keys())
        if not values_sorted:
            return None

        def delta_nominal(a: int, b: int) -> float:
            return 0.0 if a == b else 1.0

        n_freq = [n_v[v] for v in values_sorted]
        idx_map = {v: i for i, v in enumerate(values_sorted)}

        def delta_ordinal(a: int, b: int) -> float:
            i, j = idx_map[a], idx_map[b]
            if i > j:
                i, j = j, i
            s = sum(n_freq[k] for k in range(i, j + 1))
            return (s - (n_freq[i] + n_freq[j]) / 2.0) ** 2

        delta_fn = delta_nominal if level == "nominal" else delta_ordinal

        d_o = 0.0
        d_e = 0.0
        for v in values_sorted:
            for vp in values_sorted:
                o_ij = o[v][vp]
                nv = n_v[v]
                nvp = n_v[vp]
                if v == vp:
                    e_ij = nv * (nv - 1.0) / n_minus_1
                else:
                    e_ij = nv * nvp / n_minus_1
                d = delta_fn(v, vp)
                d_o += o_ij * d
                d_e += e_ij * d

        if d_e <= IAAService.EPS:
            return 1.0 if d_o <= IAAService.EPS else None
        return 1.0 - d_o / d_e

    @staticmethod
    def _dimension_agreement(
        dimension: str,
        overlap: dict[str, dict[uuid.UUID, int]],
        *,
        nominal_alpha: bool,
    ) -> DimensionAgreement:
        n_ann = len({a for m in overlap.values() for a in m})
        n_items = len(overlap)
        pct = IAAService.percentage_agreement_all_same(overlap)
        fleiss = IAAService.fleiss_kappa(overlap)
        cohen = IAAService.average_pairwise_cohens_kappa(overlap)
        alpha_level = "nominal" if nominal_alpha else "ordinal"
        alpha = IAAService.krippendorff_alpha(overlap, level=alpha_level)
        return DimensionAgreement(
            dimension=dimension,
            cohens_kappa=cohen,
            fleiss_kappa=fleiss,
            krippendorffs_alpha=alpha,
            percentage_agreement=_clamp01(pct),
            n_annotators=n_ann,
            n_items=n_items,
        )

    @staticmethod
    def compute_from_annotations(
        annotations: list[dict[str, Any]],
        *,
        task_pack_id: uuid.UUID,
        task_ids: list[str] | None = None,
    ) -> IAAResponse:
        rows = IAAService.normalize_annotation_rows(annotations)
        if task_ids is not None:
            allow = {str(x) for x in task_ids}
            rows = [r for r in rows if r["task_id"] in allow]

        all_annotators = {r["annotator_id"] for r in rows}
        n_annotators = len(all_annotators)

        def pref_getter(r: dict[str, Any]) -> int | None:
            p = r.get("preference")
            return p if isinstance(p, int) else None

        by_pref = IAAService._dedupe_per_task(rows, pref_getter)
        overlap_pref = IAAService._overlap_tasks(by_pref)

        dimension_names: set[str] = set()
        for r in rows:
            dims = r.get("dimensions")
            if isinstance(dims, dict):
                dimension_names.update(dims.keys())

        has_any_preference = any(isinstance(r.get("preference"), int) for r in rows)
        pref_block: DimensionAgreement | None = None
        if overlap_pref:
            pref_block = IAAService._dimension_agreement(
                "preference",
                overlap_pref,
                nominal_alpha=True,
            )
        elif has_any_preference:
            pref_block = DimensionAgreement(
                dimension="preference",
                cohens_kappa=None,
                fleiss_kappa=None,
                krippendorffs_alpha=None,
                percentage_agreement=0.0,
                n_annotators=n_annotators,
                n_items=0,
            )
        else:
            pref_block = None

        dim_agreements: list[DimensionAgreement] = []
        for dname in sorted(dimension_names):

            def dim_getter(r: dict[str, Any], name: str = dname) -> int | None:
                dims = r.get("dimensions")
                if not isinstance(dims, dict):
                    return None
                v = dims.get(name)
                return v if isinstance(v, int) else None

            by_dim = IAAService._dedupe_per_task(rows, dim_getter)
            overlap_d = IAAService._overlap_tasks(by_dim)
            if overlap_d:
                dim_agreements.append(
                    IAAService._dimension_agreement(dname, overlap_d, nominal_alpha=False),
                )
            else:
                dim_agreements.append(
                    DimensionAgreement(
                        dimension=dname,
                        cohens_kappa=None,
                        fleiss_kappa=None,
                        krippendorffs_alpha=None,
                        percentage_agreement=0.0,
                        n_annotators=n_annotators,
                        n_items=0,
                    ),
                )

        # Tasks with >=2 distinct annotators on any submitted row (union across rows)
        by_task_annots: dict[str, set[uuid.UUID]] = defaultdict(set)
        for r in rows:
            by_task_annots[r["task_id"]].add(r["annotator_id"])
        n_tasks_with_overlap = sum(1 for _t, s in by_task_annots.items() if len(s) >= 2)

        kappa_candidates: list[float] = []
        alpha_candidates: list[float] = []
        if pref_block and pref_block.n_items > 0:
            if pref_block.fleiss_kappa is not None:
                kappa_candidates.append(pref_block.fleiss_kappa)
            elif pref_block.cohens_kappa is not None:
                kappa_candidates.append(pref_block.cohens_kappa)
            if pref_block.krippendorffs_alpha is not None:
                alpha_candidates.append(pref_block.krippendorffs_alpha)
        for d in dim_agreements:
            if d.n_items <= 0:
                continue
            if d.fleiss_kappa is not None:
                kappa_candidates.append(d.fleiss_kappa)
            elif d.cohens_kappa is not None:
                kappa_candidates.append(d.cohens_kappa)
            if d.krippendorffs_alpha is not None:
                alpha_candidates.append(d.krippendorffs_alpha)

        overall_kappa = sum(kappa_candidates) / len(kappa_candidates) if kappa_candidates else None
        overall_alpha = sum(alpha_candidates) / len(alpha_candidates) if alpha_candidates else None

        now = datetime.now(UTC)
        return IAAResponse(
            task_pack_id=task_pack_id,
            preference_agreement=pref_block,
            dimension_agreements=dim_agreements,
            overall_kappa=overall_kappa,
            overall_alpha=overall_alpha,
            n_annotators=n_annotators,
            n_tasks_with_overlap=n_tasks_with_overlap,
            computed_at=now,
        )

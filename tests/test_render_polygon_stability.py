from __future__ import annotations

import numpy as np
import pytest

import manga_translator.rendering as rendering


def test_safe_union_polygons_recovers_from_invalid_shapes():
    _ = pytest.importorskip("shapely.geometry")

    # Self-intersecting bow-tie polygons are invalid by definition.
    bow_tie_a = np.array([[0.0, 0.0], [2.0, 2.0], [0.0, 2.0], [2.0, 0.0]], dtype=float)
    bow_tie_b = np.array([[1.0, 0.0], [3.0, 2.0], [1.0, 2.0], [3.0, 0.0]], dtype=float)

    union_poly = rendering._safe_union_polygons([bow_tie_a, bow_tie_b])

    assert union_poly is not None
    assert getattr(union_poly, "is_empty", True) is False
    assert getattr(union_poly, "geom_type", "") in {"Polygon", "MultiPolygon"}


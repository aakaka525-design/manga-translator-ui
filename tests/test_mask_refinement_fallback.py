from __future__ import annotations

import numpy as np

from manga_translator.mask_refinement import text_mask_utils as tmu


def test_refine_mask_degrades_gracefully_without_densecrf(monkeypatch):
    monkeypatch.setattr(tmu, "_DENSECRF_AVAILABLE", False)
    monkeypatch.setattr(tmu, "_DENSECRF_WARNING_EMITTED", False)
    monkeypatch.setattr(tmu, "_DENSECRF_IMPORT_ERROR", RuntimeError("missing densecrf"))

    rgb = np.zeros((20, 20, 3), dtype=np.uint8)
    rawmask = np.zeros((20, 20, 1), dtype=np.uint8)
    rawmask[4:16, 4:16, 0] = 255

    refined = tmu.refine_mask(rgb, rawmask)

    assert refined.shape == (20, 20)
    assert np.array_equal(refined, rawmask[:, :, 0])

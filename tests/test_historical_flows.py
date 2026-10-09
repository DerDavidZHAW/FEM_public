"""Unit tests for the physical-flow table built from Swissgrid metering (process.build_physical_metered)."""
import numpy as np
import pandas as pd

from data_prep.historical import process
from data_prep.historical.timeutils import hourly_index


def _overview():
    idx = hourly_index("2026-08-31", "2026-08-31")[:3]
    return pd.DataFrame({"phys_net_import_DE00": [100.0, -50.0, 0.0], "phys_net_import_FR00": [2000.0, 1500.0, np.nan],
                         "phys_net_import_IT00": [-2500.0, -2000.0, -1000.0], "phys_net_import_AT00": [10.0, 20.0, 30.0]},
                        index=idx)


def test_metered_flow_has_cbpf_columns_and_import_positive_sign():
    out = process.build_physical_metered(_overview())
    assert list(out.columns) == ["DE00", "FR00", "IT00", "AT00", "sum"]
    assert out.FR00.iloc[0] == 2000.0 and out.IT00.iloc[0] == -2500.0
    assert out["sum"].iloc[0] == 100.0 + 2000.0 - 2500.0 + 10.0


def test_metered_sum_is_missing_when_any_border_is_missing():
    out = process.build_physical_metered(_overview())
    assert np.isnan(out["sum"].iloc[2])

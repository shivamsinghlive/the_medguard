"""Stable identity for the exact dataset being audited."""
import hashlib
import json
import pandas as pd


def dataset_fingerprint(df: pd.DataFrame) -> str:
    """Identify values, row order/index, column names/order, and dtypes.

    Unlike object-array bytes, pandas hashes string contents rather than memory
    addresses. SHA-256 avoids Python's process-randomized built-in hash.
    """
    schema = json.dumps(
        {'columns': list(df.columns), 'dtypes': [str(t) for t in df.dtypes]},
        ensure_ascii=False,
    ).encode('utf-8')
    values = pd.util.hash_pandas_object(df, index=True).values.tobytes()
    return hashlib.sha256(schema + b'\0' + values).hexdigest()

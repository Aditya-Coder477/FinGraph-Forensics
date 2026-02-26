import pandas as pd
import numpy as np

def detect_smurfing(df: pd.DataFrame, time_window_hours=72, min_count=10):
    """
    Detects fan-in (many to one) and fan-out (one to many) patterns.
    Fully vectorized - no Python loops over rows.
    Returns:
    1. suspects: Dict of {acc_id: [patterns]}
    2. aggregators: List of dicts {center, type, neighbors}
    """
    suspicious_accounts = {}
    aggregators = []

    # Ensure timestamp is datetime
    if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
        df['timestamp'] = pd.to_datetime(df['timestamp'])

    time_window = pd.Timedelta(hours=time_window_hours)
    df = df.sort_values('timestamp').reset_index(drop=True)

    # ── FAN-IN: receivers getting from >= 10 unique senders in 72h ──────────
    _detect_fan(
        df, group_col='receiver_id', count_col='sender_id',
        tag='fan_in', neighbor_tag='fan_in_neighbor',
        time_window=time_window, min_count=min_count,
        suspicious_accounts=suspicious_accounts, aggregators=aggregators
    )

    # ── FAN-OUT: senders sending to >= 10 unique receivers in 72h ───────────
    _detect_fan(
        df, group_col='sender_id', count_col='receiver_id',
        tag='fan_out', neighbor_tag='fan_out_neighbor',
        time_window=time_window, min_count=min_count,
        suspicious_accounts=suspicious_accounts, aggregators=aggregators
    )

    return suspicious_accounts, aggregators


def _detect_fan(df, group_col, count_col, tag, neighbor_tag,
                time_window, min_count, suspicious_accounts, aggregators):
    """
    Vectorized: for each account in group_col, check if any 72h window
    contains >= min_count unique values in count_col.
    Uses merge-asof / groupby approach — no nested Python loops.
    """
    # Quick pre-filter: skip accounts with < min_count total unique counterparts
    total_unique = df.groupby(group_col)[count_col].nunique()
    candidates = total_unique[total_unique >= min_count].index

    if len(candidates) == 0:
        return

    df_cand = df[df[group_col].isin(candidates)].copy()
    df_cand['ts_ns'] = df_cand['timestamp'].astype('int64')
    window_ns = int(time_window.total_seconds() * 1e9)

    for account_id, group in df_cand.groupby(group_col):
        group = group.sort_values('ts_ns')
        times = group['ts_ns'].values
        ids   = group[count_col].values
        n     = len(times)

        if n < min_count:
            continue

        # Two-pointer sliding window (O(n log n) at worst, much faster than O(n²))
        found = False
        left = 0
        window_set = {}
        for right in range(n):
            cid = ids[right]
            window_set[cid] = window_set.get(cid, 0) + 1

            # Shrink left side outside window
            while times[right] - times[left] > window_ns:
                lcid = ids[left]
                window_set[lcid] -= 1
                if window_set[lcid] == 0:
                    del window_set[lcid]
                left += 1

            if len(window_set) >= min_count:
                found = True
                break

        if found:
            ptype = f'smurfing_{tag}'
            add_suspicion(suspicious_accounts, account_id, ptype)
            neighbors = group[count_col].unique().tolist()
            aggregators.append({
                "type": tag,
                "center": account_id,
                "neighbors": neighbors
            })
            for nb in neighbors:
                add_suspicion(suspicious_accounts, nb, neighbor_tag)


def add_suspicion(acc_dict, acc_id, pattern):
    if acc_id not in acc_dict:
        acc_dict[acc_id] = []
    if pattern not in acc_dict[acc_id]:
        acc_dict[acc_id].append(pattern)

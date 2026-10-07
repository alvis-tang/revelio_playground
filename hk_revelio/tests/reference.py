"""Plain-Python reference for the migration state machine (test oracle only)."""


def blocks(observations, horizon):
    """Split sorted (quarter, hk) observations into contiguous blocks up to horizon."""
    out = []
    for quarter, hk in sorted(o for o in observations if o[0] <= horizon):
        if out and quarter == out[-1][-1][0] + 1:
            out[-1].append((quarter, hk))
        else:
            out.append([(quarter, hk)])
    return out


def runs(block):
    out = []
    for quarter, hk in block:
        if out and out[-1][0] == hk:
            out[-1][2] = quarter
        else:
            out.append([hk, quarter, quarter])
    return out


def classify(observations, k, horizon):
    """Events, gap changes, excursions, unconfirmed-before-gap, and terminal pending move."""
    result = {'events': [], 'gaps': [], 'excursions': 0, 'unconfirmed_before_gap': 0, 'terminal': None}
    parts = blocks(observations, horizon)
    final = None
    for b, block in enumerate(parts):
        sequence = runs(block)
        confirmed = sequence[0][0]
        if final is not None and final != confirmed:
            result['gaps'].append((block[0][0], 'entry' if confirmed else 'exit'))
        for r, (hk, start, end) in enumerate(sequence[1:], 1):
            if hk == confirmed:
                continue
            if end - start + 1 >= k:
                result['events'].append((start, 'entry' if hk else 'exit'))
                confirmed = hk
            elif r < len(sequence) - 1:
                result['excursions'] += 1
            elif b < len(parts) - 1:
                result['unconfirmed_before_gap'] += 1
            else:
                result['terminal'] = 'entry' if hk else 'exit'
        final = confirmed
    return result

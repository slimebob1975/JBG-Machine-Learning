"""Shared read-only validation for source feature preservation in investigations."""

import pandas as pd


def validate_investigation_feature_preservation(rows, column_names, config, converted):
    """Fail closed when numeric validation destroys populated predictors.

    Compare population counts, rather than row order: DatasetHandler shuffles rows
    deterministically, and SQL/CSV both use its existing conversion path.
    A genuinely empty source column may be dropped by DatasetHandler as before.
    """
    # 299i2: the SQL data layer returns a NumPy array (the CSV layer a list);
    # "not rows" is ambiguous for an array and stopped every SQL investigation.
    if rows is None or len(rows) == 0:
        return
    if isinstance(rows, pd.DataFrame):
        raw = rows.copy()
        raw.columns = list(column_names)
    else:
        raw = pd.DataFrame.from_records(list(rows), columns=list(column_names))
    numerical = set(config.get_numerical_column_names())
    losses = []
    for name in numerical:
        if name not in raw or name not in converted:
            continue
        source = raw[name]
        valid = source.notna() & ~source.astype('string').str.strip().isin(
            ('', 'nan', 'None', 'NaT', '<NA>'))
        before = int(valid.sum())
        after = int(converted[name].notna().sum())
        if after < before:
            losses.append((name, before, after))
    if losses:
        summary = '; '.join(f'{name}: {before} nonempty source values, {after} retained'
                            for name, before, after in sorted(losses))
        raise ValueError(
            'Feature investigation rejected data lost during numeric conversion: '
            + summary + '. Check the numerical/text column roles. '
            'Select non-numeric columns as Text before investigating; '
            'no feature search was performed.')

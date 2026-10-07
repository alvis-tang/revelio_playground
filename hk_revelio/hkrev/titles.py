"""SQL expressions for auditable title-based role rules (title_taxonomy.yml)."""
from .common import lit


def normalized(column, taxonomy):
    rules = taxonomy['normalization']
    expr = column
    if rules.get('trim'):
        expr = f'trim({expr})'
    if rules.get('collapse_whitespace'):
        expr = f"regexp_replace({expr}, '\\s+', ' ', 'g')"
    if rules.get('lowercase'):
        expr = f'lower({expr})'
    for item in rules.get('replacements', []):
        expr = f"regexp_replace({expr}, {lit(item['pattern'])}, {lit(item['replacement'])}, 'g')"
    return expr


def category_match(norm, category):
    include = ' OR '.join(f'regexp_matches({norm}, {lit(r["pattern"])})' for r in category['include'])
    exclude = ' OR '.join(f'regexp_matches({norm}, {lit(r["pattern"])})' for r in category.get('exclude') or [])
    return f'(({include}) AND NOT ({exclude or "false"}))'


def rule_columns(norm, taxonomy):
    """SELECT-list SQL: role_rule_category, role_rule_ids, role_downranked.

    `norm` must be a column holding the normalized title. NULL titles match nothing.
    """
    categories = taxonomy['categories']
    whens = ' '.join(f'WHEN {category_match(norm, categories[c])} THEN {lit(c)}' for c in taxonomy['order'])
    ids = []
    for name in taxonomy['order']:
        category = categories[name]
        exclude = ' OR '.join(f'regexp_matches({norm}, {lit(r["pattern"])})' for r in category.get('exclude') or [])
        for rule in category['include']:
            ids.append(f"CASE WHEN regexp_matches({norm}, {lit(rule['pattern'])}) AND NOT ({exclude or 'false'}) "
                       f"THEN {lit(name + '/' + rule['id'])} END")
    id_list = f"list_filter([{', '.join(ids)}], x -> x IS NOT NULL)"
    return (f'CASE WHEN {norm} IS NULL THEN NULL {whens} END AS role_rule_category, '
            f'CASE WHEN {norm} IS NULL THEN []::VARCHAR[] ELSE {id_list} END AS role_rule_ids')

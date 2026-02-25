# Minimal JSONLogic-like evaluator for MVP
# Supports: and, or, not, >, >=, <, <=, ==, !=, var

def get_var(path, context):
    if isinstance(path, dict) and 'var' in path:
        path = path['var']
    if not isinstance(path, str):
        return path
    cur = context
    for part in path.split('.'):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def eval_expr(expr, context):
    if expr is None:
        return True
    if isinstance(expr, dict):
        if 'and' in expr:
            return all(eval_expr(x, context) for x in expr['and'])
        if 'or' in expr:
            return any(eval_expr(x, context) for x in expr['or'])
        if 'not' in expr:
            return not eval_expr(expr['not'], context)
        for op in ('>', '>=', '<', '<=', '==', '!='):
            if op in expr:
                a, b = expr[op]
                a = get_var(a, context)
                b = get_var(b, context)
                if op == '>': return (a or 0) > (b or 0)
                if op == '>=': return (a or 0) >= (b or 0)
                if op == '<': return (a or 0) < (b or 0)
                if op == '<=': return (a or 0) <= (b or 0)
                if op == '==': return a == b
                if op == '!=': return a != b
        if 'var' in expr:
            return get_var(expr, context)
    return expr
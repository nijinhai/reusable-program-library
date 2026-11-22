"""Runtime extension: newly synthesized functions can compose with old operators."""
from collections import deque
import time

from . import engine


def base_token(step):
    return {"base": step.as_json()}


def execute(program, value, library):
    calls = 0
    for token in program:
        if "learned" in token:
            fn = library[token["learned"]]
            value = fn.apply(value); calls += fn.cost
        else:
            spec = token["base"]
            value = engine.apply_op(engine.op(spec["op"], **spec["params"]), value); calls += 1
        if value is engine.INVALID:
            break
    return value, calls


def search(xs, ys, library=None, budget=8192):
    library = library or {}
    xs, ys = tuple(xs), tuple(ys)
    queue = deque([((), xs)])
    seen = {xs}
    best = (sum(a != b for a,b in zip(xs,ys)), 0, "[]", ())
    calls = learned_calls = 0
    exact = xs == ys
    started=time.perf_counter()
    stop="frontier_exhausted"
    base = [base_token(s) for s in engine.primitives()]
    while queue and not exact:
        program, values = queue.popleft()
        if len(program) >= 5:
            continue
        actions = [{"learned": k} for k in sorted(library)] + base
        exhausted=False
        for token in actions:
            cost = library[token["learned"]].cost if "learned" in token else 1
            if "learned" in token and learned_calls + cost*len(xs) > 1024:
                continue
            output=[]
            for value in values:
                if calls + cost > budget:
                    exhausted=True;break
                result, spent=execute((token,),value,library)
                assert spent==cost
                calls += cost
                if "learned" in token: learned_calls += cost
                output.append(result)
            if exhausted:
                stop="call_budget";queue.clear();break
            if any(v is engine.INVALID for v in output):continue
            output=tuple(output);child=program+(token,)
            error=sum(a!=b for a,b in zip(output,ys));key=(error,len(child),engine.canon(child))
            if key<best[:3]:best=(*key,child)
            if error==0:
                best=(*key,child);exact=True;stop="exact_fit";break
            if output not in seen:
                seen.add(output);queue.append((child,output))
    return {"program":best[3],"calls":calls,"learned_calls":learned_calls,"exact_fit":exact,
            "fit_errors":best[0],"stop":"exact_fit" if exact else stop,"wall_seconds":time.perf_counter()-started}


def score(program, rows, library):
    mask=[];calls=0
    for row in rows:
        output,spent=execute(program,row["input"],library);calls+=spent
        mask.append(output==row["output"])
    return mask,calls

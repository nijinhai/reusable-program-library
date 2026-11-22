from __future__ import annotations

import argparse
import json
import random
import time

from .support import ROOT, csvwrite, dump, engine, freeze, jsonlines, sha, verify, world1
from .tasks import source_task
from .synthesis import Learned, propose
from .runtime import base_token, execute, score, search

OUT=ROOT/"results"/"c_new_computation"
SEEDS=(801,802,803)
KINDS=("reverse","replace","reorder","affine")
ARMS=("BASE","REPROPOSE","LIBRARY")


def example(rng,kind,variant,category):
    a,b,c=(world1.word(rng) for _ in range(3))
    changed=category=="changed_parameters"
    if kind=="reverse":
        core=f"{a}{' ' if variant else '-'}{b}"
        if changed:core=f"{a}#{b}"
        target=core[::-1]
    elif kind=="replace":
        old,new=(('@','!') if changed else (('_',':') if variant==0 else ('#',';')))
        core=f"{a}{old}{b}{old}{c}";target=core.replace(old,new)
    elif kind=="reorder":
        sep,join,order=((';','|',(1,0)) if changed else (('|','/',(1,0)) if variant==0 else (':',' ',(2,0,1))))
        fields=[a,b,c][:len(order)];core=sep.join(fields);target=join.join(fields[i] for i in order)
    elif kind=="affine":
        n=rng.randint(100,9999);core=f"n={n}"
        scale,offset=(5,7) if changed else ((2,3) if variant==0 else (3,-2))
        target=str(scale*n+offset)
    else:
        core=a+b;target="".join(sorted(core))
    raw=f"{world1.word(rng)}/{core}" if category=="wrapped" else core
    if category=="postprocess":target=target[1:]
    return {"input":raw,"output":target}


def task(seed,phase,i,kind,variant,category):
    rng=random.Random(f"acquire-code:{seed}:{phase}:{i}")
    rows=[];seen=set()
    while len(rows)<20:
        row=example(rng,kind,variant,category)
        if row["input"] in seen:continue
        seen.add(row["input"]);rows.append(row)
    return {"task_id":f"cg-{seed}-{phase}-{i:03}","design_kind":kind,"category":category,
            "fit":rows[:4],"check":rows[4:8],"query":rows[8:]}


def worlds():
    result=[]
    for seed in SEEDS:
        sources=[task(seed,"source",i*2+j,kind,j,"direct") for i,kind in enumerate(KINDS) for j in range(2)]
        future=[]
        for ci,category in enumerate(("direct","wrapped","postprocess","changed_parameters")):
            for ki,kind in enumerate(KINDS):
                for j in range(3):
                    future.append(task(seed,"future",ci*12+ki*3+j,kind,j%2,category))
        future += [task(seed,"future",48+j,"sort",0,"outside_grammar") for j in range(4)]
        random.Random(f"acquire-order:{seed}").shuffle(future)
        result.append({"seed":seed,"history":[source_task(seed,"code_history",i) for i in range(12)],
                       "sources":sources,"future":future})
    return result


def checked_result(result,task,library):
    mask,calls=score(result["program"],task["check"],library)
    return all(mask),calls


def run():
    verify(OUT)
    if (OUT/"started.json").exists():raise RuntimeError("Do not overwrite")
    dump(OUT/"started.json",{"epoch":time.time()})
    start=time.perf_counter()
    frozen=json.loads((OUT/"tasks_frozen.json").read_text())
    programs=[];pending=[];source_records=[];births=[];costs=[];proposal_logs=[]
    for world in frozen:
        seed=world["seed"];library={};cache=[];common_calls=acquisition_calls=birth_calls=0
        for task0 in world["history"]:
            r=engine.search([x["input"] for x in task0["fit"]],[x["output"] for x in task0["fit"]],budget=32768)
            passed,fee=engine.evaluate(r["program"],task0["check"])
            common_calls+=r["calls"]+fee
            if r["exact_fit"] and all(passed):
                cache.append({"task_id":task0["task_id"],"path":r["path"]})
        for task0 in world["sources"]:
            base=search([x["input"] for x in task0["fit"]],[x["output"] for x in task0["fit"]])
            base_ok,validation=checked_result(base,task0,{})
            common_calls+=base["calls"]+validation
            acquired=None;fee={"calls":0,"attempted":0,"generated":0}
            if not (base["exact_fit"] and base_ok):
                acquired,fee=propose(task0["fit"],task0["check"])
                acquisition_calls+=fee["calls"]
            if acquired:library.setdefault(acquired.mid,acquired)
            source_records.append({"seed":seed,"task_id":task0["task_id"],"kind":task0["design_kind"],
                                   "base_found":base["exact_fit"] and base_ok,"acquired":acquired is not None,
                                   "proposal_calls":fee["calls"],"attempted":fee["attempted"],
                                   "learned_id":acquired.mid if acquired else "",
                                   "expr":acquired.expr if acquired else ""})
            if acquired:
                proposal_logs.append({"seed":seed,"task_id":task0["task_id"],"phase":"source",**acquired.packed(),"fees":fee})
        dump(OUT/f"library_{seed}.json",[v.packed() for v in library.values()])
        # Historical witnesses do not veto new capabilities.
        for candidate in library.values():
            match=neutral=mismatch=0
            for item in cache:
                for j in range(len(item["path"])-2):
                    current,goal=tuple(item["path"][j]),tuple(item["path"][j+2])
                    output=tuple(candidate.apply(x) for x in current)
                    birth_calls+=candidate.cost*len(current)
                    if output==goal:match+=1
                    elif output==current:neutral+=1
                    else:mismatch+=1
            births.append({"seed":seed,"id":candidate.mid,"kind":candidate.kind,"historical_match":match,
                           "historical_neutral":neutral,"historical_mismatch":mismatch})
        costs.append({"seed":seed,"common_old_search_calls":common_calls,"source_acquisition_calls":acquisition_calls,
                      "birth_replay_calls":birth_calls,"library_size":len(library)})
        for i,task0 in enumerate(world["future"]):
            xs,ys=[r["input"] for r in task0["fit"]],[r["output"] for r in task0["fit"]]
            base=search(xs,ys);base_ok,base_check=checked_result(base,task0,{})
            # All arms may validate returned fit candidates with the same visible check set.
            chosen_base=base["program"]
            for arm in ARMS:
                proposal_cost=0;runtime_cost=base["calls"];validation_cost=base_check;bank={};used=False
                fallback=False
                if arm=="LIBRARY":
                    r=search(xs,ys,library);bank=library
                    passed,validation_cost=checked_result(r,task0,bank)
                    runtime_cost=r["calls"]
                    selected=r["program"] if passed else chosen_base
                    if not passed:
                        fallback=True
                        runtime_cost+=base["calls"]
                        validation_cost+=base_check
                    used=any("learned" in t for t in selected)
                elif arm=="REPROPOSE" and not(base["exact_fit"] and base_ok):
                    candidate,fee=propose(task0["fit"],task0["check"])
                    proposal_cost=fee["calls"]
                    selected=chosen_base
                    if candidate:
                        bank={candidate.mid:candidate};selected=({"learned":candidate.mid},);used=True
                        proposal_logs.append({"seed":seed,"task_id":task0["task_id"],"phase":"future_repropose",**candidate.packed(),"fees":fee})
                else:selected=chosen_base
                record={"seed":seed,"task_id":task0["task_id"],"kind":task0["design_kind"],"category":task0["category"],
                        "arm":arm,"program":selected,"runtime_calls":runtime_cost,"proposal_calls":proposal_cost,
                        "validation_calls":validation_cost,"using_new_function":used,
                        "fallback_to_base":fallback,
                        "total_future_calls":runtime_cost+proposal_cost+validation_cost}
                programs.append(record);pending.append((task0,selected,bank,record))
            if (i+1)%13==0:print(f"C seed={seed} future={i+1}/52 library={len(library)}",flush=True)
    jsonlines(OUT/"programs_frozen.jsonl",programs)
    dump(OUT/"program_freeze.json",{"sha256":sha(OUT/"programs_frozen.jsonl"),"query_read":False})
    jsonlines(OUT/"proposals.jsonl",proposal_logs)
    csvwrite(OUT/"sources.csv",source_records);csvwrite(OUT/"birth.csv",births);csvwrite(OUT/"costs.csv",costs)
    rows=[];evaluation_calls=0
    for task0,program,bank,record in pending:
        masks={}
        for split in ("fit","check","query"):
            masks[split],fee=score(program,task0[split],bank);evaluation_calls+=fee
        rows.append({**record,"program":engine.canon(program),"strict":all(all(v) for v in masks.values()),
                     "query_correct":sum(masks["query"]),"masks":engine.canon(masks)})
    csvwrite(OUT/"task_results.csv",rows)
    summaries=[]
    for arm in ARMS:
        selected=[r for r in rows if r["arm"]==arm]
        acquisition=sum(c["source_acquisition_calls"] for c in costs) if arm!="BASE" else 0
        replay=sum(c["birth_replay_calls"] for c in costs) if arm=="LIBRARY" else 0
        total=sum(r["total_future_calls"] for r in selected)
        summaries.append({"arm":arm,"n":len(selected),"strict":sum(r["strict"] for r in selected),
                          "future_runtime":sum(r["runtime_calls"] for r in selected),
                          "future_proposal":sum(r["proposal_calls"] for r in selected),
                          "future_validation":sum(r["validation_calls"] for r in selected),
                          "source_acquisition":acquisition,"birth_replay":replay,"incremental_total":total+acquisition+replay,
                          "using_new_function":sum(r["using_new_function"] for r in selected)})
    csvwrite(OUT/"summary.csv",summaries)
    categories=[]
    for cat in ("direct","wrapped","postprocess","changed_parameters","outside_grammar"):
        for arm in ARMS:
            part=[r for r in rows if r["category"]==cat and r["arm"]==arm]
            categories.append({"category":cat,"arm":arm,"n":len(part),"strict":sum(r["strict"] for r in part),
                               "calls":sum(r["total_future_calls"] for r in part)})
    csvwrite(OUT/"categories.csv",categories)
    dump(OUT/"metrics.json",{"summary":summaries,"costs":costs,"categories":categories,
                             "source_acquired":sum(r["acquired"] for r in source_records),"source_n":len(source_records),
                             "offline_evaluation_calls":evaluation_calls,"wall_seconds":time.perf_counter()-start})
    lines=["# C：取得新计算并在后续复用","","受限符号元语法提案，没有外部大模型调用。元语法由研究者给定，程序及参数从fit/check选择；设计族标签不进入提案器。代码进入冻结库后，后续LIBRARY不再提案，不在线更新。","",
           "| 方法 | 严格成功/156 | 后续运行时 | 后续提案 | 后续验证 | 来源取得 | 出生回放 | 增量总计 | 使用新函数题数 |",
           "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for s in summaries:
        lines.append(f"| {s['arm']} | {s['strict']} | {s['future_runtime']} | {s['future_proposal']} | {s['future_validation']} | {s['source_acquisition']} | {s['birth_replay']} | {s['incremental_total']} | {s['using_new_function']} |")
    lines += ["","## 后续任务层","","| 层 | BASE严格/题数 | REPROPOSE严格/题数 | LIBRARY严格/题数 |","| --- | ---: | ---: | ---: |"]
    for cat in ("direct","wrapped","postprocess","changed_parameters","outside_grammar"):
        cells=[next(x for x in categories if x['category']==cat and x['arm']==arm) for arm in ARMS]
        lines.append(f"| {cat} | "+" | ".join(f"{x['strict']}/{x['n']}" for x in cells)+" |")
    lines += ["",f"来源题取得 {sum(r['acquired'] for r in source_records)}/{len(source_records)}。各路径另加共同旧求解成本 {sum(c['common_old_search_calls'] for c in costs)} 次。离线fit/check/query复核费用 {evaluation_calls} 次不进方法历史。",
              "","`proposals.jsonl`保留逐份可执行源码和提案费；`library_*.json`是冻结库；`birth.csv`给出母题前旧片段见证。没有旧match也允许新计算进入后续试用。表达式费用是声明元语法下的操作权重，不是CPU等价成本。没有为BASE重新分配同总取得预算，主表用于比较本轮策略的实际质量/成本。",""]
    (OUT/"报告.md").write_text("\n".join(lines));print("C COMPLETE",flush=True)


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("action",choices=("freeze","run"));p.add_argument("--output", type=__import__("pathlib").Path, default=ROOT.parent/"runs"/"benchmark");args=p.parse_args()
    OUT=args.output.resolve()
    if args.action=="freeze":
        freeze(OUT,"C-new-computation-v1",["C_PROTOCOL.md","c_acquire.py","c_synth.py","c_runtime.py","a_expand.py"],worlds())
        print("C FROZEN")
    else:run()

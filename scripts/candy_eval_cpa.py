#!/usr/bin/env python3
"""Codex Candy Eval - CPA API version

Tests gpt-5.5 reasoning via CPA Responses API endpoint (streaming).
Compares with/without codexcomp truncation-fold plugin.

Usage:
    python3 candy_eval_cpa.py --url http://127.0.0.1:35502/v1/responses \
        --key YOUR_KEY -n 5 -r high
"""

import argparse
import json
import re
import sys
import time
import urllib.request

CODEX_PROMPT = """不使用任何外部工具回答以下问题：

在一个黑色的袋子里放有三种口味的糖果，每种糖果有两种不同的形状（圆形和五角星形，不同的形状靠手感可以分辨）。现已知不同口味的糖和不同形状的数量统计如下表。参赛者需要在活动前决定摸出的糖果数目，那么，最少取出多少个糖果才能保证手中同时拥有不同形状的苹果味和桃子味的糖？（同时手中有圆形苹果味匹配五角星桃子味糖果，或者有圆形桃子味匹配五角星苹果味糖果都满足要求）

        苹果味  桃子味  西瓜味
圆形       7      9      8
五角星形   7      6      4
"""

ANSWER_PATTERN = re.compile(r"(?<!\d)21(?!\d)")


def run_one(url, key, model, effort):
    body = json.dumps({
        "model": model,
        "stream": True,
        "input": [{"type": "message", "role": "user",
                   "content": [{"type": "input_text", "text": CODEX_PROMPT}]}],
        "reasoning": {"effort": effort},
    }).encode()

    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
            "Accept": "text/event-stream",
        },
    )

    start = time.perf_counter()
    text = ""
    usage = {}
    meta = {}

    with urllib.request.urlopen(req, timeout=300) as resp:
        buf = b""
        for chunk in iter(lambda: resp.read(4096), b""):
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.strip()
                if not line.startswith(b"data:"):
                    continue
                data_str = line[5:].strip()
                if data_str == b"[DONE]":
                    break
                try:
                    ev = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                etype = ev.get("type", "")
                if etype == "response.output_text.delta":
                    text += ev.get("delta", "")
                elif etype in ("response.completed", "response.failed", "response.incomplete"):
                    r = ev.get("response", {})
                    usage = r.get("usage", {})
                    meta = r.get("metadata", {})
                elif etype == "response.output_item.done":
                    item = ev.get("item", {})
                    if item.get("type") == "message":
                        for part in item.get("content", []):
                            if part.get("type") == "output_text":
                                text += part.get("text", "")
    elapsed = time.perf_counter() - start

    in_tok = usage.get("input_tokens", 0)
    out_tok = usage.get("output_tokens", 0)
    rea_tok = usage.get("output_tokens_details", {}).get("reasoning_tokens", 0)

    rounds = meta.get("proxy_rounds", [])
    stopped = meta.get("proxy_stopped_reason", "")

    return text, in_tok, out_tok, rea_tok, elapsed, rounds, stopped


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("-m", "--model", default="gpt-5.5")
    parser.add_argument("-r", "--reasoning-effort", default="high",
                        choices=["low", "medium", "high"])
    parser.add_argument("-n", "--tests", type=int, default=1)
    parser.add_argument("--label", default="", help="label for this run")
    args = parser.parse_args()

    print(f"{'Run':>3}  {'OK':^3}  {'InTok':>6}  {'OutTok':>6}  {'ReaTok':>6}  "
          f"{'Time':>6}  {'TPS':>6}  {'Rounds':>6}  {'Stopped':>20}  Answer")
    print("-" * 100)

    results = []
    for i in range(1, args.tests + 1):
        try:
            text, in_tok, out_tok, rea_tok, elapsed, rounds, stopped = \
                run_one(args.url, args.key, args.model, args.reasoning_effort)
            tps = f"{out_tok / elapsed:.1f}" if out_tok and elapsed > 0 else "-"
            ok = bool(ANSWER_PATTERN.search(text))
            n_rounds = len(rounds) if rounds else 1
            preview = text[:50].replace("\n", " ")
            print(f"{i:>3}  {'✓' if ok else '✗':^3}  {in_tok:>6}  {out_tok:>6}  "
                  f"{rea_tok:>6}  {elapsed:>6.1f}  {tps:>6}  {n_rounds:>6}  "
                  f"{stopped or '-':>20}  {preview}")
            results.append({"ok": ok, "rea_tok": rea_tok, "rounds": n_rounds,
                            "time": elapsed, "stopped": stopped})
        except Exception as e:
            print(f"{i:>3}  ERR  {str(e)[:80]}")
            results.append({"ok": False, "error": str(e)})

    print("-" * 100)
    correct = sum(1 for r in results if r.get("ok"))
    label = f" [{args.label}]" if args.label else ""
    print(f"\n{label} Graded {len(results)}/{args.tests}  "
          f"correct={correct}  accuracy={correct/len(results)*100:.1f}%")

    # Save raw results
    import json as _json
    with open(f"candy_eval_results{label.replace(' ','_').replace('[','_').replace(']','')}.json", "w") as f:
        _json.dump({"label": args.label, "results": results}, f, indent=2, ensure_ascii=False)
    print(f"Results saved to candy_eval_results{label.replace(' ','_').replace('[','_').replace(']','')}.json")


if __name__ == "__main__":
    main()

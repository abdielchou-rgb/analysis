#!/usr/bin/env python3
"""circuit_monitor.py — LLM Provider Circuit Breaker 监控面板。

实时显示各 provider 的熔断状态、连续失败数、冷却时间。

用法:
    python scripts/circuit_monitor.py
    python scripts/circuit_monitor.py --json
    python scripts/circuit_monitor.py --reset zhipu
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.smart_router import get_router


def get_provider_status() -> list[dict]:
    """获取所有 provider 的熔断状态。"""
    router = get_router()
    result = []
    for name, config in router._configs.items():
        failures = router._failures.get(name, 0)
        broken_until = router._circuit_broken_until.get(name, 0)
        now = time.time()
        in_cooldown = broken_until > now
        cooldown_remaining = max(0, broken_until - now) if in_cooldown else 0
        priority = config.priority
        models = config.models if hasattr(config, "models") else []

        result.append(
            {
                "name": name,
                "priority": priority,
                "models": len(models),
                "failures": failures,
                "in_cooldown": in_cooldown,
                "cooldown_remaining": round(cooldown_remaining, 1),
                "status": "BROKEN" if in_cooldown else ("DEGRADED" if failures >= 3 else "HEALTHY"),
            }
        )
    return sorted(result, key=lambda x: x["priority"])


def print_panel(statuses: list[dict]):
    """打印监控面板。"""
    print("=" * 60)
    print("  LLM Provider Circuit Breaker Monitor")
    print("=" * 60)
    print()

    for s in statuses:
        status_icon = {
            "HEALTHY": "[OK]",
            "DEGRADED": "[!!]",
            "BROKEN": "[XX]",
        }.get(s["status"], "[??]")

        cooldown_str = ""
        if s["in_cooldown"]:
            mins = int(s["cooldown_remaining"] // 60)
            secs = int(s["cooldown_remaining"] % 60)
            cooldown_str = f" COOLDOWN {mins}m{secs}s"

        print(
            f"  {status_icon} {s['name']:20s} P{s['priority']}  "
            f"failures={s['failures']:.1f}  "
            f"models={s['models']}{cooldown_str}"
        )

    print()
    healthy = sum(1 for s in statuses if s["status"] == "HEALTHY")
    degraded = sum(1 for s in statuses if s["status"] == "DEGRADED")
    broken = sum(1 for s in statuses if s["status"] == "BROKEN")
    print(f"  Summary: {healthy} healthy, {degraded} degraded, {broken} broken")
    print("=" * 60)


def reset_provider(name: str):
    """重置指定 provider 的熔断状态。"""
    router = get_router()
    if name in router._failures:
        router._failures[name] = 0
        router._circuit_broken_until[name] = 0
        print(f"[OK] Reset {name}: failures=0, cooldown cleared")
    else:
        print(f"[!!] Provider {name} not found")


def main():
    parser = argparse.ArgumentParser(description="LLM Provider Circuit Breaker Monitor")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--reset", help="重置指定 provider 的熔断状态")
    args = parser.parse_args()

    if args.reset:
        reset_provider(args.reset)
        return

    statuses = get_provider_status()

    if args.json:
        print(json.dumps(statuses, indent=2))
    else:
        print_panel(statuses)


if __name__ == "__main__":
    main()

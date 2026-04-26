#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════╗
║         🍽️  AI Meal Planner — CLI (No API)          ║
║   Works fully offline using heuristic AI scoring    ║
╚══════════════════════════════════════════════════════╝

Usage:
    python meal_planner_cli.py                  # interactive mode
    python meal_planner_cli.py --help           # show options

    python meal_planner_cli.py \
        --budget 3000 --diet Veg --days 7 \
        --disease Diabetes --output plan.txt
"""

import argparse
import os
import sys
import textwrap

# ── Path setup so we can import agent.py from backend/ ───────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(SCRIPT_DIR, "backend"))
from agent import MealPlannerAgent, DISEASE_RULES

# ── Colour helpers (graceful degradation on Windows) ─────────────────────────
try:
    import ctypes
    ctypes.windll.kernel32.SetConsoleMode(ctypes.windll.kernel32.GetStdHandle(-11), 7)
except Exception:
    pass

BOLD   = "\033[1m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RED    = "\033[91m"
DIM    = "\033[2m"
RESET  = "\033[0m"

SLOT_ICONS = {"Breakfast": "🌅", "Lunch": "☀️", "Dinner": "🌙"}

# ─────────────────────────────────────────────────────────────────────────────

def divider(char="─", width=60, color=DIM):
    print(f"{color}{char * width}{RESET}")

def header(text, color=CYAN):
    divider("═", color=color)
    print(f"{color}{BOLD}  {text}{RESET}")
    divider("═", color=color)

def section(text, color=YELLOW):
    print(f"\n{color}{BOLD}▶ {text}{RESET}")
    divider(color=DIM)

# ─────────────────────────────────────────────────────────────────────────────

def print_plan(result: dict, show_ingredients: bool = True):
    summary = result["summary"]
    plan    = result["plan"]
    grocery = result["grocery_list"]

    # ── Summary banner ────────────────────────────────────────────────────────
    header("📊  PLAN SUMMARY")
    within = summary["within_budget"]
    bcolor = GREEN if within else RED
    print(f"  Diet type   : {BOLD}{summary['diet_type']}{RESET}")
    print(f"  Days        : {BOLD}{summary['num_days']}{RESET}")
    if summary.get("disease"):
        print(f"  Condition   : {YELLOW}{summary['disease']}{RESET}")
    print(f"  Budget      : {BOLD}₹{summary['budget']:,.0f}{RESET}")
    print(f"  Total cost  : {bcolor}{BOLD}₹{summary['total_cost_inr']:,.0f}{RESET}  "
          f"({'✅ within budget' if within else '⚠️ over budget'})")
    print(f"  Saved/Over  : {bcolor}₹{abs(summary['budget_remaining_inr']):,.0f}{RESET}")
    print(f"  Avg/day cost: ₹{summary['avg_daily_cost_inr']:,.0f}")
    print(f"  Total cal   : {summary['total_calories_kcal']:,.0f} kcal")
    print(f"  Avg cal/day : {summary['avg_daily_calories_kcal']:,.0f} kcal")
    print()
    if summary.get("ai_summary"):
        print(f"  {DIM}{textwrap.fill(summary['ai_summary'], 56, subsequent_indent='  ')}{RESET}")

    # ── Day-by-day plan ───────────────────────────────────────────────────────
    section("📅  MEAL PLAN")
    for day_data in plan:
        print(f"\n  {CYAN}{BOLD}Day {day_data['day']}{RESET}  "
              f"{DIM}| ₹{day_data['day_cost_inr']}  "
              f"| {day_data['day_calories_kcal']:,.0f} kcal{RESET}")
        for slot, meal in day_data["meals"].items():
            icon  = SLOT_ICONS.get(slot, "🍽️")
            hmark = f"{GREEN}✅{RESET}" if meal["is_healthy"] else ""
            print(f"    {icon} {YELLOW}{slot:<10}{RESET}  "
                  f"{BOLD}{meal['meal_name']:<35}{RESET}  "
                  f"₹{meal['cost_inr']:<5}  "
                  f"{meal['estimated_calories_kcal']:.0f} kcal  "
                  f"{hmark}")
            if show_ingredients:
                ing_str = ", ".join(meal["ingredients"])
                print(f"              {DIM}{textwrap.fill(ing_str, 50, subsequent_indent=' ' * 14)}{RESET}")

    # ── Grocery list ──────────────────────────────────────────────────────────
    section("🛒  GROCERY LIST")
    print(f"  {len(grocery)} unique ingredients\n")
    cols = 3
    chunk = max(1, len(grocery) // cols + 1)
    rows  = [grocery[i:i+chunk] for i in range(0, len(grocery), chunk)]
    max_rows = max(len(r) for r in rows)
    for ri in range(max_rows):
        line_parts = []
        for col in rows:
            if ri < len(col):
                g = col[ri]
                line_parts.append(
                    f"  {CYAN}•{RESET} {g['ingredient']:<22} {DIM}×{g['frequency']}{RESET}"
                )
            else:
                line_parts.append(" " * 28)
        print("".join(line_parts))

    # ── Health note ───────────────────────────────────────────────────────────
    if summary.get("disease_note"):
        print(f"\n  {YELLOW}⚕️  Health note:{RESET} {summary['disease_note']}")

    divider("═", color=CYAN)

# ─────────────────────────────────────────────────────────────────────────────

def interactive_mode(agent: MealPlannerAgent):
    header("🍽️   AI MEAL PLANNER  —  Offline Mode")

    # ── Budget ────────────────────────────────────────────────────────────────
    while True:
        try:
            budget = float(input(f"\n  {BOLD}💰 Total budget (₹): {RESET}").strip())
            if budget <= 0:
                raise ValueError
            break
        except ValueError:
            print(f"  {RED}Enter a positive number.{RESET}")

    # ── Diet type ─────────────────────────────────────────────────────────────
    while True:
        raw = input(f"  {BOLD}🥗 Diet type [Veg / Non-veg]: {RESET}").strip().lower()
        if raw in ("veg", "v"):
            diet_type = "Veg"; break
        elif raw in ("non-veg", "nonveg", "n", "non"):
            diet_type = "Non-veg"; break
        print(f"  {RED}Type 'Veg' or 'Non-veg'.{RESET}")

    # ── Days ──────────────────────────────────────────────────────────────────
    while True:
        try:
            num_days = int(input(f"  {BOLD}📅 Number of days (1–14): {RESET}").strip())
            if 1 <= num_days <= 14:
                break
            raise ValueError
        except ValueError:
            print(f"  {RED}Enter a whole number between 1 and 14.{RESET}")

    # ── Disease ───────────────────────────────────────────────────────────────
    diseases = ["None"] + [d.title() for d in DISEASE_RULES.keys()]
    print(f"\n  {BOLD}⚕️  Health condition (optional):{RESET}")
    for i, d in enumerate(diseases):
        print(f"    {DIM}[{i}]{RESET}  {d}")
    while True:
        raw = input(f"  Choose [0–{len(diseases)-1}] or type name (default 0): ").strip()
        if raw == "" or raw == "0":
            disease = None; break
        if raw.isdigit() and 0 <= int(raw) < len(diseases):
            disease = None if int(raw) == 0 else diseases[int(raw)]; break
        # allow typing
        match = next((d for d in diseases if d.lower() == raw.lower()), None)
        if match:
            disease = None if match == "None" else match; break
        print(f"  {RED}Invalid choice.{RESET}")

    # ── Generate ──────────────────────────────────────────────────────────────
    print(f"\n  {DIM}Generating your meal plan…{RESET}")
    try:
        result = agent.generate_plan(
            budget=budget,
            diet_type=diet_type,
            num_days=num_days,
            disease=disease,
            seed=None,          # random seed = fresh plan every time
        )
    except ValueError as e:
        print(f"\n  {RED}⚠️  {e}{RESET}\n")
        return

    print_plan(result)

    # ── Post-plan options ─────────────────────────────────────────────────────
    while True:
        print(f"\n  {BOLD}What next?{RESET}")
        print(f"  {DIM}[r]{RESET} Re-plan (fresh selection)  "
              f"{DIM}[q]{RESET} Ask a question  "
              f"{DIM}[s]{RESET} Save to file  "
              f"{DIM}[x]{RESET} Exit")
        choice = input("  → ").strip().lower()

        if choice == "r":
            print(f"\n  {DIM}Re-generating…{RESET}")
            result = agent.generate_plan(
                budget=budget, diet_type=diet_type,
                num_days=num_days, disease=disease, seed=None,
            )
            print_plan(result)

        elif choice == "q":
            question = input(f"\n  {BOLD}Your question: {RESET}").strip()
            if question:
                answer = agent.chat(question, result["summary"])
                print(f"\n  {CYAN}🤖 {textwrap.fill(answer, 56, subsequent_indent='     ')}{RESET}")

        elif choice == "s":
            fname = input("  Filename [plan.txt]: ").strip() or "plan.txt"
            save_plan_to_file(result, fname)
            print(f"  {GREEN}✅ Saved to {fname}{RESET}")

        elif choice == "x":
            print(f"\n  {GREEN}Goodbye! Eat healthy! 🥗{RESET}\n")
            break
        else:
            print(f"  {RED}Unknown option.{RESET}")

# ─────────────────────────────────────────────────────────────────────────────

def save_plan_to_file(result: dict, path: str):
    """Save a plain-text version of the plan (no ANSI colour codes)."""
    summary = result["summary"]
    plan    = result["plan"]
    grocery = result["grocery_list"]

    lines = []
    lines.append("=" * 60)
    lines.append("  AI MEAL PLANNER — PLAN SUMMARY")
    lines.append("=" * 60)
    lines.append(f"  Diet     : {summary['diet_type']}")
    lines.append(f"  Days     : {summary['num_days']}")
    if summary.get("disease"):
        lines.append(f"  Condition: {summary['disease']}")
    lines.append(f"  Budget   : Rs {summary['budget']:,.0f}")
    lines.append(f"  Cost     : Rs {summary['total_cost_inr']:,.0f}  "
                 f"({'within budget' if summary['within_budget'] else 'OVER budget'})")
    lines.append(f"  Calories : {summary['total_calories_kcal']:,.0f} kcal total  "
                 f"(~{summary['avg_daily_calories_kcal']:,.0f}/day)")
    if summary.get("ai_summary"):
        lines.append("")
        lines.append(textwrap.fill(summary["ai_summary"], 58))
    lines.append("")
    lines.append("─" * 60)
    lines.append("  MEAL PLAN")
    lines.append("─" * 60)
    for day_data in plan:
        lines.append(f"\nDay {day_data['day']}  |  Rs {day_data['day_cost_inr']}  |  {day_data['day_calories_kcal']:.0f} kcal")
        for slot, meal in day_data["meals"].items():
            lines.append(f"  {slot:<10}  {meal['meal_name']:<35}  Rs {meal['cost_inr']}")
            lines.append(f"             Ingredients: {', '.join(meal['ingredients'])}")
            lines.append(f"             Calories: {meal['estimated_calories_kcal']:.0f} kcal  |  "
                         f"Protein: {meal['protein']:.2f}  Fat: {meal['fat']:.2f}  Carbs: {meal['carbs']:.2f}")
    lines.append("")
    lines.append("─" * 60)
    lines.append("  GROCERY LIST")
    lines.append("─" * 60)
    for g in grocery:
        lines.append(f"  • {g['ingredient']:<25}  x{g['frequency']}")
    if summary.get("disease_note"):
        lines.append("")
        lines.append(f"  Health note: {summary['disease_note']}")
    lines.append("=" * 60)

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

# ─────────────────────────────────────────────────────────────────────────────

def cli_mode(args):
    """Non-interactive mode driven by command-line flags."""
    agent = MealPlannerAgent()
    disease = args.disease if args.disease and args.disease.lower() != "none" else None

    print(f"\n  {DIM}Generating {args.days}-day {args.diet} plan on ₹{args.budget} budget…{RESET}")
    try:
        result = agent.generate_plan(
            budget=float(args.budget),
            diet_type=args.diet,
            num_days=int(args.days),
            disease=disease,
            seed=args.seed,
        )
    except ValueError as e:
        print(f"\n  {RED}⚠️  {e}{RESET}\n")
        sys.exit(1)

    print_plan(result, show_ingredients=not args.no_ingredients)

    if args.output:
        save_plan_to_file(result, args.output)
        print(f"\n  {GREEN}✅ Plan saved to {args.output}{RESET}\n")

# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="AI Meal Planner — fully offline, no API required.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              python meal_planner_cli.py                         # interactive
              python meal_planner_cli.py --budget 3000 --diet Veg --days 7
              python meal_planner_cli.py --budget 5000 --diet Non-veg --days 5 --disease Diabetes
              python meal_planner_cli.py --budget 2500 --diet Veg --days 3 --output my_plan.txt
        """),
    )
    parser.add_argument("--budget",          type=float, help="Total budget in INR")
    parser.add_argument("--diet",            type=str,   help="Veg or Non-veg")
    parser.add_argument("--days",            type=int,   help="Number of days (1–14)")
    parser.add_argument("--disease",         type=str,   help="Health condition (optional)", default=None)
    parser.add_argument("--output",          type=str,   help="Save plan to this file", default=None)
    parser.add_argument("--seed",            type=int,   help="Random seed for reproducibility", default=None)
    parser.add_argument("--no-ingredients",  action="store_true", help="Hide ingredient lists")

    args = parser.parse_args()

    # If all required flags provided → CLI mode, else interactive
    if args.budget and args.diet and args.days:
        agent = MealPlannerAgent()
        cli_mode(args)
    else:
        agent = MealPlannerAgent()
        interactive_mode(agent)


if __name__ == "__main__":
    main()

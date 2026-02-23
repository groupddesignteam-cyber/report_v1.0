import os
from pathlib import Path
import pandas as pd

path = os.environ["TARGET_XLSX"]
blog_reservation_count = float(os.environ.get("BLOG_RESERVATION_COUNT", "1"))

raw = pd.read_excel(path, sheet_name=0, header=2)
df = raw.iloc[:, 0:11].copy()
df.columns = [
    "type", "category", "item", "owner_dept", "status", "executor",
    "cost_excl_labor", "price_vat_excl", "posting_ratio", "replacement_per_posting", "note"
]

for c in ["type", "category", "item", "owner_dept", "status", "executor", "note"]:
    df[c] = df[c].astype(str).str.strip().replace({"nan": "", "None": ""})

df["owner_dept"] = (
    df["owner_dept"]
    .str.replace(r"\s*,\s*", ", ", regex=True)
    .str.replace(r"\s+", " ", regex=True)
    .str.strip()
)

for c in ["type", "category", "owner_dept"]:
    df[c] = df[c].replace("", pd.NA).ffill().fillna("")

for c in ["posting_ratio", "replacement_per_posting", "cost_excl_labor", "price_vat_excl"]:
    df[c] = pd.to_numeric(df[c], errors="coerce")

calc = df[df["replacement_per_posting"].notna()].copy()
calc = calc[calc["item"].astype(str).str.strip() != ""]
calc["blog_reservation_count"] = blog_reservation_count
calc["needed_count_vs_blog_reservations"] = calc["replacement_per_posting"] * blog_reservation_count


def summarize(col: str) -> pd.DataFrame:
    g = (
        calc.groupby(col, dropna=False)
        .agg(
            item_count=("item", "count"),
            avg_replacement_per_posting=("replacement_per_posting", "mean"),
            sum_replacement_per_posting=("replacement_per_posting", "sum"),
            min_replacement_per_posting=("replacement_per_posting", "min"),
            max_replacement_per_posting=("replacement_per_posting", "max"),
            needed_count_sum=("needed_count_vs_blog_reservations", "sum"),
        )
        .reset_index()
        .sort_values("needed_count_sum", ascending=False)
    )
    return g

sum_category = summarize("category")
sum_item = summarize("item")
sum_owner = summarize("owner_dept")
sum_status = summarize("status")
sum_executor = summarize("executor")
sum_replacement = summarize("replacement_per_posting")

out_dir = Path(r"C:/Users/WD/Downloads/report/analysis_output")
out_dir.mkdir(exist_ok=True)
out_path = out_dir / "replacement_plan_vs_blog_reservations.xlsx"

with pd.ExcelWriter(out_path, engine="openpyxl") as w:
    calc.to_excel(w, sheet_name="base_cleaned", index=False)
    sum_category.to_excel(w, sheet_name="by_category", index=False)
    sum_item.to_excel(w, sheet_name="by_item", index=False)
    sum_owner.to_excel(w, sheet_name="by_owner_dept", index=False)
    sum_status.to_excel(w, sheet_name="by_status", index=False)
    sum_executor.to_excel(w, sheet_name="by_executor", index=False)
    sum_replacement.to_excel(w, sheet_name="by_replacement_value", index=False)

print(f"BASE_ROWS={len(calc)}")
print(f"OUT={out_path}")
print("STATUS_SUMMARY")
print(sum_status.to_string(index=False))
print("OWNER_SUMMARY")
print(sum_owner.to_string(index=False))

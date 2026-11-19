import re
from datetime import datetime

SCHEME_ROW = re.compile(r"^(\d+);([^;]*);([^;]*);([^;]*);([^;]*)")


def parse_navall(text: str) -> list[dict]:
    amc = ""
    scheme_category = ""
    schemes = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if ";" not in line:
            amc = line if line else amc
            continue
        match = SCHEME_ROW.match(line)
        if not match:
            continue
        code, isin_div_payout, isin_reinvest, name, nav = match.groups()
        parts = line.split(";")
        nav_value = parts[4].strip() if len(parts) > 4 else ""
        nav_date = parts[-1].strip() if len(parts) > 5 else ""
        try:
            parsed_date = datetime.strptime(nav_date, "%d-%b-%Y").date()
            parsed_nav = float(nav_value)
        except (ValueError, IndexError):
            continue
        if parsed_nav <= 0:
            continue
        lname = name.lower()
        plan = "direct" if "direct" in lname else "regular" if "regular" in lname else "unknown"
        option = "growth" if "growth" in lname else "idcw" if "dividend" in lname or "idcw" in lname else "bonus" if "bonus" in lname else "unknown"
        schemes.append({
            "scheme_code": int(code),
            "name": name.strip(),
            "amc": amc,
            "category_raw": scheme_category,
            "plan": plan,
            "option": option,
            "nav": parsed_nav,
            "nav_date": parsed_date,
        })
    return schemes

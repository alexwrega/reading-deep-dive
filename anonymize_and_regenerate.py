#!/usr/bin/env python3
"""Anonymize student names (First Name + Last Initial) and regenerate all HTML pages."""

import json
import re
import os

DATA_FILE = "/Users/alexandra/Documents/Claude/deep_dive_data.json"
OUT_DIR = "/Users/alexandra/Documents/Claude/deep_dive_report/students"
INDEX_FILE = "/Users/alexandra/Documents/Claude/deep_dive_report/index.html"

with open(DATA_FILE, "r", encoding="utf-8") as f:
    students = json.load(f)

def anonymize_name(full_name):
    """Convert 'Love Lalla-Pagan' to 'Love L.'"""
    parts = full_name.strip().split()
    if len(parts) == 1:
        return parts[0]
    first = parts[0]
    last_initial = parts[-1][0].upper()
    return f"{first} {last_initial}."

def slugify(name):
    """Create URL-safe slug from anonymized name."""
    s = name.lower().replace("ö", "oe").replace(" ", "_").replace(".", "")
    s = re.sub(r'[^a-z0-9_-]', '', s)
    return s

# Create name mapping
name_map = {}
for student in students:
    original = student["name"]
    anon = anonymize_name(original)
    name_map[original] = anon
    student["original_name"] = original
    student["name"] = anon

print("Name mapping:")
for orig, anon in name_map.items():
    print(f"  {orig} -> {anon}")

# Sort by growth ascending (worst first)
students.sort(key=lambda s: s["growth"] if s["growth"] is not None else 999)

def fmt_num(v, decimals=0):
    if v is None or v == "" or v == "n/a":
        return "&mdash;"
    try:
        v = float(v)
        if decimals == 0:
            return f"{int(round(v)):,}"
        return f"{v:,.{decimals}f}"
    except:
        return str(v)

def growth_class(g):
    if g is None: return ""
    if g < 0: return "growth-neg"
    if g == 0: return "growth-zero"
    return "growth-pos"

def growth_display(g):
    if g is None: return "&mdash;"
    if g > 0: return f"+{int(g)}"
    return str(int(g))

def pct_class(p):
    if p is None: return ""
    if p < 75: return "pct-warn"
    if p >= 100: return "pct-ok"
    return ""

ISSUE_LABELS = {
    "NO_INSTRUCTION_APP": ("No Instruction App (G9+)", "tag-red"),
    "SHOULD_HAVE_MOBYMAX": ("Needs MobyMax", "tag-orange"),
    "OVER_TESTING": ("Over-Testing", "tag-red"),
    "DOOM_LOOP": ("Doom Loop", "tag-red"),
    "LOW_MINUTES": ("Low Minutes", "tag-orange"),
    "AT_GRADE_NO_MOTIVATION": ("At/Ahead of Grade", "tag-blue"),
    "LARGE_GAP_OVERWHELMED": ("Large Gap", "tag-purple"),
    "LOW_EFFECTIVE_TESTS": ("Low Effective Tests", "tag-gray"),
    "POSSIBLE_MID_SEMESTER": ("Possible Mid-Semester", "tag-gray"),
}

def get_recommendation(student):
    """Generate personalized recommendation based on issues."""
    recs = []
    issues = student.get("issues", [])
    name_first = student["name"].split()[0]

    if "NO_INSTRUCTION_APP" in issues:
        recs.append(f"{name_first} has surpassed MobyMax's G8 ceiling and has no reading instruction app. Assign a G9+ reading resource (e.g., Newsela, CommonLit) immediately. In the interim, ensure Alpha Read usage is structured with specific reading goals and comprehension checks.")

    if "SHOULD_HAVE_MOBYMAX" in issues:
        recs.append(f"{name_first} is within MobyMax range (G3-G8) but is not currently assigned. Add MobyMax to their learning plan immediately to supplement Alpha Read with structured reading instruction.")

    if "OVER_TESTING" in issues:
        pct = student.get("pct_testing", 0)
        recs.append(f"{name_first} is spending {pct:.0f}% of XP on testing apps instead of learning. Cap testing to 1 attempt per grade per week and redirect time to Alpha Read and MobyMax instruction.")

    if "DOOM_LOOP" in issues:
        grades = student.get("doom_grades", [])
        grade_str = ", ".join([f"G{g}" for g in grades])
        recs.append(f"{name_first} is stuck in a test doom loop ({grade_str}). Break the cycle: require at least 2 weeks of focused instruction in Alpha Read/MobyMax before any retest attempt. Review whether the student has knowledge gaps that need targeted instruction.")

    if "LOW_MINUTES" in issues:
        pct = student.get("pct_expected", 0)
        recs.append(f"{name_first} is only at {pct:.0f}% of expected reading time ({fmt_num(student['reading_mins'])} of 2,150 min). Investigate barriers to time on task: scheduling conflicts, engagement issues, or behavioral concerns. Set a daily check-in to ensure 25 min/day minimum.")

    if "AT_GRADE_NO_MOTIVATION" in issues and "NO_INSTRUCTION_APP" not in issues:
        recs.append(f"{name_first} is at or ahead of grade level but showing negative growth, suggesting low motivation. Consider reading enrichment, student-choice reading, or challenge-level content to re-engage.")

    if "LARGE_GAP_OVERWHELMED" in issues:
        gap = student.get("gap", 0)
        recs.append(f"{name_first} has a {int(gap) if gap else '?'}-grade gap to age grade. Create a structured catch-up plan with achievable weekly milestones. Celebrate progress (e.g., passing a grade test) to build momentum. Consider whether the current material level is appropriate.")

    if "LOW_EFFECTIVE_TESTS" in issues and "OVER_TESTING" not in issues and "DOOM_LOOP" not in issues:
        eff = student.get("eff_rate", 0)
        recs.append(f"{name_first} has a {eff:.0f}% effective test rate. Many test attempts are unproductive. Ensure the student completes all required instruction before testing. Review test readiness criteria.")

    if not recs:
        recs.append(f"{name_first} met time expectations and has reasonable app distribution but still showed limited growth. Investigate engagement quality: is the student actively reading or passively spending time? Consider a one-on-one reading conference to assess comprehension skills directly.")

    return recs

def generate_app_bar(student):
    """Generate stacked bar chart HTML for app XP distribution."""
    total = student.get("total_xp", 0)
    if total == 0:
        return '<div class="bar-bg"><div class="bar-fill admin" style="width:100%"></div></div><div class="bar-legend">No XP data</div>'

    instr = student.get("instr_xp", 0)
    test = student.get("testing_xp", 0)
    elit = student.get("elit_xp", 0)
    admin = student.get("admin_xp", 0)

    pct_i = (instr / total) * 100
    pct_t = (test / total) * 100
    pct_e = (elit / total) * 100
    pct_a = (admin / total) * 100

    bar = f'''<div class="stacked-bar">
      <div class="bar-seg instr" style="width:{pct_i:.1f}%" title="Instruction: {fmt_num(instr)} XP ({pct_i:.0f}%)"></div>
      <div class="bar-seg test" style="width:{pct_t:.1f}%" title="Testing: {fmt_num(test)} XP ({pct_t:.0f}%)"></div>
      <div class="bar-seg elit" style="width:{pct_e:.1f}%" title="Early Lit: {fmt_num(elit)} XP ({pct_e:.0f}%)"></div>
      <div class="bar-seg admin" style="width:{pct_a:.1f}%" title="Admin/Other: {fmt_num(admin)} XP ({pct_a:.0f}%)"></div>
    </div>'''
    return bar

def build_nav(current_slug):
    """Build prev/next navigation."""
    idx = None
    for i, s in enumerate(students):
        if slugify(s["name"]) == current_slug:
            idx = i
            break
    prev_link = ""
    next_link = ""
    if idx is not None:
        if idx > 0:
            ps = students[idx - 1]
            prev_link = f'<a href="{slugify(ps["name"])}.html" class="nav-link">&larr; {ps["name"]}</a>'
        if idx < len(students) - 1:
            ns = students[idx + 1]
            next_link = f'<a href="{slugify(ns["name"])}.html" class="nav-link">{ns["name"]} &rarr;</a>'
    return prev_link, next_link


# Generate student pages
for student in students:
    slug = slugify(student["name"])
    prev_link, next_link = build_nav(slug)
    recs = get_recommendation(student)

    # Build app details table rows
    app_rows = ""
    for app in sorted(student.get("app_details", []), key=lambda a: -a["xp"]):
        total = student.get("total_xp", 1)
        pct = (app["xp"] / total * 100) if total > 0 else 0
        app_name = app["app"]
        if app_name in ["Alpha Read", "MobyMax"]:
            cat = "Instruction"
            cat_class = "tag-green"
        elif app_name in ["Mastery Track", "100 for 100", "Alpha Tests"]:
            cat = "Testing"
            cat_class = "tag-orange"
        elif app_name in ["Anton", "ClearFluency", "Amplify", "Mentava", "Literably", "Lalilo", "Lexia Core5", "FastPhonics", "TeachTales"]:
            cat = "Early Lit"
            cat_class = "tag-purple"
        else:
            cat = "Other"
            cat_class = "tag-gray"
        app_rows += f'''<tr>
          <td>{app_name}</td>
          <td><span class="tag {cat_class}">{cat}</span></td>
          <td>{fmt_num(app["xp"])}</td>
          <td>{pct:.1f}%</td>
        </tr>'''

    # Test history section
    test_section = ""
    if student.get("total_tests", 0) > 0:
        doom_str = ""
        if student.get("doom_grades"):
            doom_str = f'<div class="alert alert-red">Doom loop detected on grade(s): {", ".join(["G"+str(g) for g in student["doom_grades"]])}</div>'

        test_grades_str = ", ".join([f"G{g}" for g in student.get("test_grades", [])])
        test_section = f'''
        <div class="metric-card full-width">
          <h3>Test History</h3>
          {doom_str}
          <div class="metric-grid">
            <div class="metric"><div class="metric-val">{student["total_tests"]}</div><div class="metric-label">Total Tests</div></div>
            <div class="metric"><div class="metric-val">{student["eff_tests"]}</div><div class="metric-label">Effective Tests</div></div>
            <div class="metric"><div class="metric-val {pct_class(student["eff_rate"]) if student["eff_rate"] else ''}">{fmt_num(student["eff_rate"])}%</div><div class="metric-label">Effective Rate</div></div>
            <div class="metric"><div class="metric-val">{fmt_num(student["avg_accuracy"])}%</div><div class="metric-label">Avg Accuracy</div></div>
          </div>
          <p class="detail-line"><strong>Grades tested:</strong> {test_grades_str}</p>
          <p class="detail-line"><strong>First test date:</strong> {student.get("first_test", "N/A")}</p>
        </div>'''
    else:
        test_section = '''
        <div class="metric-card full-width">
          <h3>Test History</h3>
          <p class="detail-line muted">No reading tests taken during this period.</p>
        </div>'''

    # Year-over-year section
    yoy_section = ""
    if student.get("spring_rit"):
        slide = student.get("summer_slide")
        slide_str = ""
        if slide is not None:
            if slide > 0:
                slide_str = f'<span class="growth-neg">Lost {int(slide)} RIT over summer</span>'
            elif slide < 0:
                slide_str = f'<span class="growth-pos">Gained {int(abs(slide))} RIT over summer</span>'
            else:
                slide_str = '<span>No summer change</span>'
        yoy_section = f'''
        <div class="metric-card">
          <h3>Year-over-Year</h3>
          <div class="rit-timeline">
            <div class="rit-point"><div class="rit-val">{student["spring_rit"]}</div><div class="rit-label">Spring 25</div></div>
            <div class="rit-arrow">&rarr;</div>
            <div class="rit-point"><div class="rit-val">{student["fall_rit"]}</div><div class="rit-label">Fall 25</div></div>
            <div class="rit-arrow">&rarr;</div>
            <div class="rit-point"><div class="rit-val">{student["winter_rit"]}</div><div class="rit-label">Winter 26</div></div>
          </div>
          <p class="detail-line" style="margin-top:10px;">{slide_str}</p>
        </div>'''
    else:
        yoy_section = f'''
        <div class="metric-card">
          <h3>Year-over-Year</h3>
          <div class="rit-timeline">
            <div class="rit-point muted"><div class="rit-val">&mdash;</div><div class="rit-label">Spring 25</div></div>
            <div class="rit-arrow">&rarr;</div>
            <div class="rit-point"><div class="rit-val">{student["fall_rit"]}</div><div class="rit-label">Fall 25</div></div>
            <div class="rit-arrow">&rarr;</div>
            <div class="rit-point"><div class="rit-val">{student["winter_rit"]}</div><div class="rit-label">Winter 26</div></div>
          </div>
          <p class="detail-line muted" style="margin-top:10px;">No Spring 2025 score (likely new to Alpha)</p>
        </div>'''

    # Issues tags
    issue_tags = ""
    for issue in student.get("issues", []):
        label, cls = ISSUE_LABELS.get(issue, (issue, "tag-gray"))
        issue_tags += f'<span class="tag {cls}">{label}</span> '

    # Comments section - anonymize any names in comments
    comments_section = ""
    if student.get("comments") and student["comments"].strip():
        comments_text = student["comments"]
        # Don't include comments in public version (may contain identifying info)
        comments_section = ""

    # Recommendations
    recs_html = ""
    for i, r in enumerate(recs, 1):
        recs_html += f'<li>{r}</li>'

    # Beyond MobyMax flag
    moby_flag = ""
    if student.get("beyond_moby"):
        moby_flag = '<div class="alert alert-red">Beyond MobyMax ceiling (G8) &mdash; no reading instruction app available</div>'
    elif student.get("in_range_no_moby"):
        moby_flag = '<div class="alert alert-orange">Within MobyMax range but NOT currently assigned to MobyMax</div>'

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{student["name"]} - Deep Dive Profile</title>
<style>
  :root {{
    --red: #e74c3c; --orange: #f39c12; --yellow: #f1c40f; --green: #27ae60;
    --blue: #2980b9; --dark: #2c3e50; --light: #ecf0f1; --bg: #f8f9fa;
    --card-bg: #fff; --text: #333; --muted: #7f8c8d;
  }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; }}
  .container {{ max-width: 960px; margin: 0 auto; padding: 20px; }}

  .profile-header {{ background: var(--dark); color: white; padding: 24px 0; margin-bottom: 24px; }}
  .profile-header .container {{ display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; }}
  .profile-header h1 {{ font-size: 1.5rem; }}
  .profile-header .grade-badge {{ background: rgba(255,255,255,0.15); padding: 4px 14px; border-radius: 16px; font-size: 0.85rem; }}
  .nav-bar {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 8px; }}
  .nav-link {{ color: var(--blue); text-decoration: none; font-size: 0.9rem; }}
  .nav-link:hover {{ text-decoration: underline; }}
  .back-link {{ font-weight: 600; }}

  .growth-hero {{ display: flex; gap: 20px; margin-bottom: 24px; flex-wrap: wrap; }}
  .growth-box {{ background: var(--card-bg); border-radius: 10px; padding: 20px; box-shadow: 0 2px 6px rgba(0,0,0,0.06); text-align: center; flex: 1; min-width: 140px; }}
  .growth-box .big-num {{ font-size: 2.2rem; font-weight: 800; }}
  .growth-box .label {{ font-size: 0.8rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; }}
  .growth-neg {{ color: var(--red); }}
  .growth-zero {{ color: var(--orange); }}
  .growth-pos {{ color: var(--green); }}
  .pct-warn {{ color: var(--red); font-weight: 600; }}
  .pct-ok {{ color: var(--green); }}

  .metric-card {{ background: var(--card-bg); border-radius: 10px; padding: 20px; box-shadow: 0 2px 6px rgba(0,0,0,0.06); margin-bottom: 20px; }}
  .metric-card.full-width {{ grid-column: 1 / -1; }}
  .metric-card h3 {{ font-size: 1rem; margin-bottom: 12px; color: var(--dark); border-bottom: 2px solid var(--light); padding-bottom: 6px; }}
  .metric-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(100px, 1fr)); gap: 16px; }}
  .metric {{ text-align: center; }}
  .metric-val {{ font-size: 1.5rem; font-weight: 700; }}
  .metric-label {{ font-size: 0.75rem; color: var(--muted); text-transform: uppercase; }}
  .detail-line {{ font-size: 0.88rem; margin: 6px 0; }}
  .detail-line strong {{ color: var(--dark); }}
  .muted {{ color: var(--muted); }}

  .stacked-bar {{ display: flex; height: 24px; border-radius: 6px; overflow: hidden; background: #e8e8e8; margin: 10px 0; }}
  .bar-seg {{ height: 100%; transition: width 0.3s; }}
  .bar-seg.instr {{ background: var(--green); }}
  .bar-seg.test {{ background: var(--orange); }}
  .bar-seg.elit {{ background: #9b59b6; }}
  .bar-seg.admin {{ background: #95a5a6; }}
  .bar-legend {{ display: flex; gap: 14px; flex-wrap: wrap; font-size: 0.78rem; margin-top: 6px; }}
  .legend-dot {{ display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 4px; vertical-align: middle; }}

  .tag {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 0.72rem; font-weight: 600; margin: 1px 2px; }}
  .tag-red {{ background: #fde8e8; color: #c0392b; }}
  .tag-orange {{ background: #fef3e2; color: #e67e22; }}
  .tag-blue {{ background: #e8f0fe; color: #2471a3; }}
  .tag-purple {{ background: #f0e6f6; color: #7d3c98; }}
  .tag-gray {{ background: #eee; color: #666; }}
  .tag-green {{ background: #e8f8e8; color: #1e8449; }}

  .alert {{ padding: 10px 14px; border-radius: 8px; font-size: 0.85rem; margin-bottom: 14px; font-weight: 500; }}
  .alert-red {{ background: #fde8e8; color: #c0392b; border-left: 4px solid var(--red); }}
  .alert-orange {{ background: #fef3e2; color: #e67e22; border-left: 4px solid var(--orange); }}

  .app-table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
  .app-table th {{ text-align: left; font-size: 0.75rem; text-transform: uppercase; color: var(--muted); padding: 6px 8px; border-bottom: 2px solid var(--light); }}
  .app-table td {{ padding: 8px; font-size: 0.85rem; border-bottom: 1px solid #f0f0f0; }}

  .rit-timeline {{ display: flex; align-items: center; gap: 12px; justify-content: center; flex-wrap: wrap; }}
  .rit-point {{ text-align: center; }}
  .rit-val {{ font-size: 1.4rem; font-weight: 700; }}
  .rit-label {{ font-size: 0.72rem; color: var(--muted); text-transform: uppercase; }}
  .rit-arrow {{ font-size: 1.2rem; color: var(--muted); }}

  .rec-card {{ background: #e8f8e8; border-radius: 10px; padding: 20px; margin-bottom: 20px; border-left: 5px solid var(--green); }}
  .rec-card h3 {{ color: #1e8449; margin-bottom: 10px; font-size: 1rem; }}
  .rec-card ol {{ padding-left: 20px; }}
  .rec-card li {{ margin-bottom: 8px; font-size: 0.88rem; }}

  .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
  @media (max-width: 700px) {{ .two-col {{ grid-template-columns: 1fr; }} }}

  .footer {{ text-align: center; color: var(--muted); font-size: 0.8rem; padding: 30px 0; }}
</style>
</head>
<body>

<div class="profile-header">
  <div class="container">
    <h1>{student["name"]}</h1>
    <div>
      <span class="grade-badge">Grade {student["age_grade"]}</span>
      <span class="grade-badge">RIT {student["fall_rit"]} &rarr; {student["winter_rit"]}</span>
    </div>
  </div>
</div>

<div class="container">

<div class="nav-bar">
  <a href="../index.html" class="nav-link back-link">&larr; Back to Executive Summary</a>
  <div>
    {prev_link}
    {' &nbsp;|&nbsp; ' if prev_link and next_link else ''}
    {next_link}
  </div>
</div>

{moby_flag}

<div style="margin-bottom: 16px;">
  {issue_tags if issue_tags.strip() else '<span class="tag tag-gray">No critical flags</span>'}
</div>

<div class="growth-hero">
  <div class="growth-box">
    <div class="big-num {growth_class(student['growth'])}">{growth_display(student['growth'])}</div>
    <div class="label">RIT Growth (F&rarr;W)</div>
  </div>
  <div class="growth-box">
    <div class="big-num {pct_class(student['pct_expected'])}">{fmt_num(student['pct_expected'])}%</div>
    <div class="label">% Expected Time</div>
  </div>
  <div class="growth-box">
    <div class="big-num">{fmt_num(student['pct_instr'])}%</div>
    <div class="label">Instruction XP</div>
  </div>
  <div class="growth-box">
    <div class="big-num">{fmt_num(student.get('gap', None))}</div>
    <div class="label">Grade Gap (HMG to Age)</div>
  </div>
</div>

<div class="rec-card">
  <h3>Recommendations</h3>
  <ol>
    {recs_html}
  </ol>
</div>

{comments_section}

<div class="two-col">
  <div class="metric-card">
    <h3>Time on Task</h3>
    <div class="metric-grid">
      <div class="metric"><div class="metric-val">{fmt_num(student['reading_mins'])}</div><div class="metric-label">Reading Min</div></div>
      <div class="metric"><div class="metric-val">2,150</div><div class="metric-label">Expected Min</div></div>
      <div class="metric"><div class="metric-val {pct_class(student['pct_expected'])}">{fmt_num(student['pct_expected'])}%</div><div class="metric-label">% of Expected</div></div>
      <div class="metric"><div class="metric-val">{fmt_num(student['daily_avg'], 1)}</div><div class="metric-label">Daily Avg Min</div></div>
    </div>
  </div>
  {yoy_section}
</div>

<div class="metric-card">
  <h3>XP Breakdown by Category</h3>
  {generate_app_bar(student)}
  <div class="bar-legend">
    <span><span class="legend-dot" style="background:var(--green);"></span> Instruction ({fmt_num(student['instr_xp'])} XP, {fmt_num(student['pct_instr'])}%)</span>
    <span><span class="legend-dot" style="background:var(--orange);"></span> Testing ({fmt_num(student['testing_xp'])} XP, {fmt_num(student['pct_testing'])}%)</span>
    {'<span><span class="legend-dot" style="background:#9b59b6;"></span> Early Lit (' + fmt_num(student['elit_xp']) + ' XP)</span>' if student.get('elit_xp', 0) > 0 else ''}
    {'<span><span class="legend-dot" style="background:#95a5a6;"></span> Other (' + fmt_num(student['admin_xp']) + ' XP)</span>' if student.get('admin_xp', 0) > 0 else ''}
  </div>
  <table class="app-table">
    <thead><tr><th>App</th><th>Category</th><th>XP</th><th>% of Total</th></tr></thead>
    <tbody>{app_rows}</tbody>
  </table>
</div>

{test_section}

<div class="metric-card">
  <h3>Session 2 Diagnostic Flags</h3>
  <div class="metric-grid">
    <div class="metric"><div class="metric-val">{"Yes" if student.get("put_time") == "Yes" else '<span class="pct-warn">No</span>'}</div><div class="metric-label">Put in Time?</div></div>
    <div class="metric"><div class="metric-val">{"Yes" if student.get("earned_xp_flag") == "Yes" else '<span class="pct-warn">No</span>'}</div><div class="metric-label">Earned XP?</div></div>
    <div class="metric"><div class="metric-val">{student.get("eff_mastered", "0")}</div><div class="metric-label">Grades Mastered</div></div>
    <div class="metric"><div class="metric-val">{"Yes" if student.get("mastered_1") == "Yes" else '<span class="pct-warn">No</span>'}</div><div class="metric-label">Mastered &ge;1?</div></div>
  </div>
</div>

</div>

<div class="footer">
  Deep Dive Profile &middot; Alpha Austin MS &middot; Winter 2025-26 MAP
</div>

</body>
</html>'''

    filepath = os.path.join(OUT_DIR, f"{slug}.html")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Generated: {slug}.html")

# Delete old student files that used full names
old_files = [
    "love_lalla-pagan.html", "kanhai_shah.html", "eddie_margain-junco.html",
    "rhys_bjoerendahl.html", "byron_attridge.html", "armin_rouwet.html",
    "gwendolyn_meegan.html", "bobbi_brown.html", "jack_cotner.html",
    "parker_carlson.html", "elena_mentgen.html", "kai_sticker.html",
    "roarke_radia.html", "sam_ratcliff.html", "luke_hock.html",
    "nathan_scharf.html", "jack_bromberg.html", "valentina_melendez.html",
    "aileya_klinefelter.html", "nadine_romman.html", "tyson_karp.html"
]
for old_file in old_files:
    old_path = os.path.join(OUT_DIR, old_file)
    if os.path.exists(old_path):
        os.remove(old_path)
        print(f"  Removed old file: {old_file}")

print(f"\nGenerated {len(students)} anonymized student pages.")

# Now regenerate index.html with anonymized names
# Build student rows for the table
def get_first_name(name):
    return name.split()[0]

table_rows = ""
for s in students:
    slug = slugify(s["name"])

    # Issue tags
    tags = ""
    if "NO_INSTRUCTION_APP" in s.get("issues", []):
        tags += '<span class="tag tag-red">No Instr App</span> '
    if "SHOULD_HAVE_MOBYMAX" in s.get("issues", []):
        tags += '<span class="tag tag-orange">Needs MobyMax</span> '
    if "OVER_TESTING" in s.get("issues", []):
        tags += '<span class="tag tag-red">Over-Testing</span> '
    if "DOOM_LOOP" in s.get("issues", []):
        doom_g = s.get("doom_grades", [])
        if doom_g:
            tags += f'<span class="tag tag-red">Doom Loop G{doom_g[0]}</span> '
    if "LOW_MINUTES" in s.get("issues", []):
        tags += '<span class="tag tag-orange">Low Min</span> '
    if "AT_GRADE_NO_MOTIVATION" in s.get("issues", []) and "NO_INSTRUCTION_APP" not in s.get("issues", []):
        tags += '<span class="tag tag-blue">At Grade</span> '
    if "LARGE_GAP_OVERWHELMED" in s.get("issues", []):
        tags += '<span class="tag tag-purple">Large Gap</span> '
    if "LOW_EFFECTIVE_TESTS" in s.get("issues", []) and "OVER_TESTING" not in s.get("issues", []) and "DOOM_LOOP" not in s.get("issues", []):
        tags += '<span class="tag tag-gray">Low Eff Tests</span> '
    if not tags.strip():
        tags = '<span class="tag tag-gray">Quality Issue</span>'

    eff_rate_display = f'{s["eff_rate"]:.0f}%' if s.get("eff_rate") else "&mdash;"
    eff_class = "pct-warn" if s.get("eff_rate") is not None and s["eff_rate"] < 50 else ""

    table_rows += f'''<tr>
        <td><a class="student-link" href="students/{slug}.html">{s["name"]}</a></td>
        <td>{s["age_grade"]}</td>
        <td class="{growth_class(s['growth'])}">{growth_display(s['growth'])}</td>
        <td>{s["fall_rit"]} &rarr; {s["winter_rit"]}</td>
        <td>{fmt_num(s["reading_mins"])}</td>
        <td class="{pct_class(s['pct_expected'])}">{fmt_num(s['pct_expected'])}%</td>
        <td>{fmt_num(s["instr_xp"])}</td>
        <td>{fmt_num(s["testing_xp"])}</td>
        <td class="{'' if s['pct_instr'] >= 50 else 'pct-warn'}">{fmt_num(s['pct_instr'])}%</td>
        <td>{s["total_tests"]}</td>
        <td class="{eff_class}">{eff_rate_display}</td>
        <td>{tags}</td>
      </tr>'''

# Build cluster names (anonymized)
no_instr_names = ", ".join([get_first_name(s["name"]) for s in students if "NO_INSTRUCTION_APP" in s.get("issues", [])])
overtest_names = ", ".join([get_first_name(s["name"]) for s in students if "OVER_TESTING" in s.get("issues", []) or "DOOM_LOOP" in s.get("issues", [])])
low_min_names = ", ".join([get_first_name(s["name"]) for s in students if "LOW_MINUTES" in s.get("issues", [])])
moby_names = ", ".join([get_first_name(s["name"]) for s in students if "SHOULD_HAVE_MOBYMAX" in s.get("issues", [])])
gap_names = ", ".join([get_first_name(s["name"]) for s in students if "LARGE_GAP_OVERWHELMED" in s.get("issues", [])])

# Affected lists for issue cards
beyond_moby_list = ", ".join([s["name"] for s in students if s.get("beyond_moby")])
should_moby_list = ", ".join([s["name"] for s in students if s.get("in_range_no_moby")])
overtest_list = ", ".join([f'{s["name"]} ({s["pct_testing"]:.0f}% test XP)' for s in students if s.get("pct_testing", 0) > 50])
doom_list = ", ".join([f'{s["name"]} (G{s["doom_grades"][0]})' for s in students if s.get("doom_grades")])

index_html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Deep Dive: Low/No Growth Reading - Alpha Austin MS</title>
<style>
  :root {{
    --red: #e74c3c; --orange: #f39c12; --yellow: #f1c40f; --green: #27ae60;
    --blue: #2980b9; --dark: #2c3e50; --light: #ecf0f1; --bg: #f8f9fa;
    --card-bg: #ffffff; --text: #333; --muted: #7f8c8d;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}

  header {{ background: var(--dark); color: white; padding: 30px 0; margin-bottom: 30px; }}
  header .container {{ display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; }}
  header h1 {{ font-size: 1.6rem; font-weight: 700; }}
  header .subtitle {{ color: #bdc3c7; font-size: 0.95rem; }}
  .stats-bar {{ display: flex; gap: 20px; flex-wrap: wrap; }}
  .stat-pill {{ background: rgba(255,255,255,0.1); padding: 6px 14px; border-radius: 20px; font-size: 0.85rem; }}
  .stat-pill strong {{ color: var(--yellow); }}

  .issue-section {{ margin-bottom: 40px; }}
  .issue-section h2 {{ font-size: 1.3rem; margin-bottom: 20px; color: var(--dark); border-bottom: 3px solid var(--red); display: inline-block; padding-bottom: 4px; }}
  .issue-cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 20px; }}
  .issue-card {{ background: var(--card-bg); border-radius: 10px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); border-left: 5px solid var(--red); }}
  .issue-card.orange {{ border-left-color: var(--orange); }}
  .issue-card.yellow {{ border-left-color: var(--yellow); }}
  .issue-card h3 {{ font-size: 1.1rem; margin-bottom: 8px; }}
  .issue-card .issue-num {{ display: inline-block; background: var(--red); color: white; width: 28px; height: 28px; line-height: 28px; text-align: center; border-radius: 50%; font-weight: 700; font-size: 0.85rem; margin-right: 8px; }}
  .issue-card.orange .issue-num {{ background: var(--orange); }}
  .issue-card.yellow .issue-num {{ background: var(--yellow); }}
  .issue-card p {{ font-size: 0.9rem; color: #555; margin-bottom: 10px; }}
  .issue-card .affected {{ font-size: 0.82rem; color: var(--muted); }}
  .issue-card .affected strong {{ color: var(--dark); }}
  .issue-card .metric-row {{ display: flex; gap: 15px; margin: 12px 0; flex-wrap: wrap; }}
  .mini-metric {{ background: var(--bg); padding: 6px 12px; border-radius: 6px; font-size: 0.82rem; }}
  .mini-metric .val {{ font-weight: 700; font-size: 1rem; }}

  .students-section {{ margin-bottom: 40px; }}
  .students-section h2 {{ font-size: 1.3rem; margin-bottom: 16px; color: var(--dark); border-bottom: 3px solid var(--blue); display: inline-block; padding-bottom: 4px; }}
  table {{ width: 100%; border-collapse: collapse; background: var(--card-bg); border-radius: 10px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
  thead {{ background: var(--dark); color: white; }}
  th {{ padding: 12px 10px; text-align: left; font-size: 0.78rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; white-space: nowrap; }}
  td {{ padding: 10px 10px; font-size: 0.85rem; border-bottom: 1px solid #eee; }}
  tr:hover {{ background: #f0f4f8; }}
  .growth-neg {{ color: var(--red); font-weight: 700; }}
  .growth-zero {{ color: var(--orange); font-weight: 700; }}
  .growth-pos {{ color: var(--green); font-weight: 700; }}
  .pct-warn {{ color: var(--red); font-weight: 600; }}
  .pct-ok {{ color: var(--green); }}
  .tag {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 0.7rem; font-weight: 600; margin: 1px 2px; white-space: nowrap; }}
  .tag-red {{ background: #fde8e8; color: #c0392b; }}
  .tag-orange {{ background: #fef3e2; color: #e67e22; }}
  .tag-blue {{ background: #e8f0fe; color: #2471a3; }}
  .tag-purple {{ background: #f0e6f6; color: #7d3c98; }}
  .tag-gray {{ background: #eee; color: #666; }}
  a.student-link {{ color: var(--blue); text-decoration: none; font-weight: 600; }}
  a.student-link:hover {{ text-decoration: underline; }}

  .cluster-section {{ margin-bottom: 40px; }}
  .cluster-section h2 {{ font-size: 1.3rem; margin-bottom: 16px; color: var(--dark); border-bottom: 3px solid var(--orange); display: inline-block; padding-bottom: 4px; }}
  .cluster-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 16px; }}
  .cluster-card {{ background: var(--card-bg); border-radius: 10px; padding: 18px; box-shadow: 0 2px 6px rgba(0,0,0,0.06); text-align: center; }}
  .cluster-card h4 {{ font-size: 0.95rem; margin-bottom: 4px; }}
  .cluster-card .count {{ font-size: 2rem; font-weight: 800; margin: 6px 0; }}
  .cluster-card .names {{ font-size: 0.78rem; color: var(--muted); }}
  .cluster-card.cl-red {{ border-top: 4px solid var(--red); }}
  .cluster-card.cl-red .count {{ color: var(--red); }}
  .cluster-card.cl-orange {{ border-top: 4px solid var(--orange); }}
  .cluster-card.cl-orange .count {{ color: var(--orange); }}
  .cluster-card.cl-yellow {{ border-top: 4px solid var(--yellow); }}
  .cluster-card.cl-yellow .count {{ color: var(--yellow); }}
  .cluster-card.cl-blue {{ border-top: 4px solid var(--blue); }}
  .cluster-card.cl-blue .count {{ color: var(--blue); }}
  .cluster-card.cl-purple {{ border-top: 4px solid #8e44ad; }}
  .cluster-card.cl-purple .count {{ color: #8e44ad; }}

  .footer {{ text-align: center; color: var(--muted); font-size: 0.8rem; padding: 30px 0; }}

  @media (max-width: 768px) {{
    .issue-cards {{ grid-template-columns: 1fr; }}
    table {{ font-size: 0.75rem; }}
    th, td {{ padding: 6px 5px; }}
  }}
</style>
</head>
<body>

<header>
  <div class="container">
    <div>
      <h1>Deep Dive: Low/No Growth Reading Students</h1>
      <div class="subtitle">Alpha Austin Middle School &middot; Winter 2025-26 MAP Analysis</div>
    </div>
    <div class="stats-bar">
      <div class="stat-pill"><strong>21</strong> students</div>
      <div class="stat-pill">Avg growth: <strong>-2.9 RIT</strong></div>
      <div class="stat-pill">86 school days analyzed</div>
      <div class="stat-pill">Aug 14 &ndash; Jan 23</div>
    </div>
  </div>
</header>

<div class="container">

<section class="issue-section">
  <h2>Top 3 Systemic Issues</h2>
  <div class="issue-cards">

    <div class="issue-card">
      <h3><span class="issue-num">1</span>No Instruction App for G9+ Students</h3>
      <p>MobyMax caps at G8. Students who have mastered G8+ have <strong>no reading instruction app</strong> &mdash; only Alpha Read remains, which provides limited instructional scaffolding at this level.</p>
      <div class="metric-row">
        <div class="mini-metric"><div class="val">5</div>students affected</div>
        <div class="mini-metric"><div class="val">-5.0</div>avg growth</div>
        <div class="mini-metric"><div class="val">3 more</div>in MobyMax range but not assigned</div>
      </div>
      <div class="affected">
        <strong>Beyond MobyMax:</strong> {beyond_moby_list}<br>
        <strong>Should have MobyMax:</strong> {should_moby_list}
      </div>
      <p style="margin-top:10px;"><strong>Recommendation:</strong> Urgently source a G9+ reading instruction app. Assign the 3 eligible students to MobyMax immediately.</p>
    </div>

    <div class="issue-card orange">
      <h3><span class="issue-num">2</span>Over-Testing &amp; Test Doom Loops</h3>
      <p>Testing is assessment, not learning. Students trapped in test cycles accumulate XP but <strong>receive no instruction</strong>. 14 of 20 tested students have &lt;50% effective test rate.</p>
      <div class="metric-row">
        <div class="mini-metric"><div class="val">2</div>severely over-testing (&gt;50% test XP)</div>
        <div class="mini-metric"><div class="val">3</div>in doom loops</div>
        <div class="mini-metric"><div class="val">14/20</div>&lt;50% effective test rate</div>
      </div>
      <div class="affected">
        <strong>Over-testing:</strong> {overtest_list}<br>
        <strong>Doom loops:</strong> {doom_list}
      </div>
      <p style="margin-top:10px;"><strong>Recommendation:</strong> Cap testing to 1 attempt per grade per week. Break doom loops by requiring 2 weeks of instruction before retesting.</p>
    </div>

    <div class="issue-card yellow">
      <h3><span class="issue-num">3</span>Minutes &ne; Growth &mdash; Quality of Engagement</h3>
      <p>11 of 21 students met or exceeded the 2,150-minute target, yet 9 of those 11 still had <strong>negative growth</strong>. Time alone is not the problem.</p>
      <div class="metric-row">
        <div class="mini-metric"><div class="val">11/21</div>met time target</div>
        <div class="mini-metric"><div class="val">9/11</div>still declined</div>
        <div class="mini-metric"><div class="val">r = -0.17</div>minutes vs growth</div>
      </div>
      <div class="affected">
        <strong>Contributing factors:</strong> At/ahead-of-grade students lack motivation. Students 3+ grades behind are overwhelmed.
      </div>
      <p style="margin-top:10px;"><strong>Recommendation:</strong> Shift from tracking minutes to tracking instructional quality. For at-grade students, introduce enrichment. For large-gap students, create structured catch-up plans.</p>
    </div>

  </div>
</section>

<section class="cluster-section">
  <h2>Student Clusters</h2>
  <div class="cluster-grid">
    <div class="cluster-card cl-red">
      <h4>No Instruction App (G9+)</h4>
      <div class="count">5</div>
      <div class="names">{no_instr_names}</div>
    </div>
    <div class="cluster-card cl-orange">
      <h4>Over-Testing / Doom Loop</h4>
      <div class="count">3</div>
      <div class="names">{overtest_names}</div>
    </div>
    <div class="cluster-card cl-yellow">
      <h4>Low Minutes (&lt;75%)</h4>
      <div class="count">5</div>
      <div class="names">{low_min_names}</div>
    </div>
    <div class="cluster-card cl-blue">
      <h4>Should Have MobyMax</h4>
      <div class="count">3</div>
      <div class="names">{moby_names}</div>
    </div>
    <div class="cluster-card cl-purple">
      <h4>Large Gap / Overwhelmed</h4>
      <div class="count">4</div>
      <div class="names">{gap_names}</div>
    </div>
  </div>
</section>

<section class="students-section">
  <h2>All 21 Students &mdash; Sorted by Growth</h2>
  <div style="overflow-x:auto;">
  <table>
    <thead>
      <tr>
        <th>Student</th>
        <th>Gr</th>
        <th>Growth</th>
        <th>Fall&rarr;Win RIT</th>
        <th>Read Min</th>
        <th>% Expected</th>
        <th>Instr XP</th>
        <th>Test XP</th>
        <th>% Instr</th>
        <th>Tests</th>
        <th>Eff%</th>
        <th>Issues</th>
      </tr>
    </thead>
    <tbody>
      {table_rows}
    </tbody>
  </table>
  </div>
</section>

<section class="issue-section">
  <h2>Key Data Points</h2>
  <div class="issue-cards">
    <div class="issue-card" style="border-left-color: var(--blue);">
      <h3>Minutes vs Growth</h3>
      <p>Correlation between reading minutes and growth is <strong>r = -0.17</strong> (not statistically significant). More time does not predict better outcomes.</p>
      <p>XP vs growth: <strong>r = 0.44, p = 0.048</strong> (weakly significant).</p>
    </div>
    <div class="issue-card" style="border-left-color: #8e44ad;">
      <h3>Year-over-Year Context</h3>
      <p>14 students have Spring 2025 scores. Average summer slide was <strong>-0.5 RIT</strong>. 7 students are new to Alpha (no prior scores).</p>
    </div>
    <div class="issue-card" style="border-left-color: var(--green);">
      <h3>Effective Test Rate</h3>
      <p>14 of 20 tested students have &lt;50% effective test rate. 8 students have 0% effective rate &mdash; every test was unproductive.</p>
    </div>
  </div>
</section>

</div>

<div class="footer">
  Deep Dive Analysis &middot; Alpha Austin MS &middot; Winter 2025-26 MAP &middot; Generated Feb 2026
</div>

</body>
</html>'''

with open(INDEX_FILE, "w", encoding="utf-8") as f:
    f.write(index_html)
print(f"\nRegenerated index.html with anonymized names.")

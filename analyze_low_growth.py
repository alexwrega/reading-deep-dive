#!/usr/bin/env python3
"""
Deep Dive Analysis: Low/No Growth Reading Students - Alpha Austin MS
Analyzes 21 low/no-growth middle school reading students (Winter 25-26)
"""

import pandas as pd
import numpy as np
from datetime import date, timedelta
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

DATA_DIR = "/Users/alexandra/Documents/Claude"

# ============================================================
# STEP 1: DATA LOADING & CLEANING
# ============================================================
print("=" * 80)
print("LOADING DATA FILES")
print("=" * 80)

# 1a. Deep Dive file
deep_dive = pd.read_csv(
    f"{DATA_DIR}/Combined DeepDive - Low_No Growth Alpha Austin MS Winter 25-26 - Retakes G3+.csv",
    encoding='utf-8'
)
print(f"Deep Dive: {len(deep_dive)} rows loaded")

# 1b. XP file
xp_data = pd.read_csv(
    f"{DATA_DIR}/Combined DeepDive - Low_No Growth Alpha Austin MS Winter 25-26 - Weekly XP per Student_Subject - All.csv",
    encoding='utf-8'
)
xp_data['xp_earned (SUM)'] = pd.to_numeric(xp_data['xp_earned (SUM)'], errors='coerce').fillna(0)
print(f"XP Data: {len(xp_data)} rows loaded, {xp_data['fullname'].nunique()} unique students")

# 1c. Minutes file
minutes_data = pd.read_csv(
    f"{DATA_DIR}/Combined DeepDive - Low_No Growth Alpha Austin MS Winter 25-26 - Weekly minutes per student_subject - All.csv",
    encoding='utf-8'
)
minutes_data['active_minutes (SUM)'] = pd.to_numeric(minutes_data['active_minutes (SUM)'], errors='coerce').fillna(0)
print(f"Minutes Data: {len(minutes_data)} rows loaded, {minutes_data['fullname'].nunique()} unique students")

# 1d. Test history
test_history = pd.read_csv(f"{DATA_DIR}/Test School Year.csv", encoding='utf-8')
test_history['Submission Date'] = pd.to_datetime(test_history['Submission Date'])
test_history['Accuracy'] = pd.to_numeric(test_history['Accuracy'], errors='coerce')
test_history['Effective Test?'] = pd.to_numeric(test_history['Effective Test?'], errors='coerce')
print(f"Test History: {len(test_history)} rows loaded, {test_history['Student'].nunique()} unique students")

# 1e. Spring MAP scores
spring_map = pd.read_csv(f"{DATA_DIR}/Last Years Spring MAP Scores.csv", encoding='utf-8')
spring_map_reading = spring_map[spring_map['Subject'] == 'Reading'].copy()
spring_map_reading['Spring 2425 RIT'] = pd.to_numeric(spring_map_reading['Spring 2425 RIT'], errors='coerce')
print(f"Spring MAP: {len(spring_map_reading)} reading scores loaded")

# 1f. Define deep-dive students and their data from the main file
# Clean up the deep dive - the Student Name column is what we need
dd_students = deep_dive['Student Name'].dropna().unique().tolist()
print(f"\nDeep Dive Students ({len(dd_students)}): {dd_students}")

# Build a name mapping for fuzzy matching across files
# Deep dive names -> other file names
NAME_MAP = {
    'Bobbi Brown': ['Bobbi Brown', 'Bobbi Sue Brown'],
    'Nathan Scharf': ['Nathan Scharf', 'Nathaniel Scharf'],
    'Rhys Björendahl': ['Rhys Björendahl', 'Rhys Bjorendahl'],
}

def find_student_in_df(student_name, df, name_col):
    """Find a student in a dataframe, trying exact match first then fuzzy."""
    # Exact match
    matches = df[df[name_col] == student_name]
    if len(matches) > 0:
        return matches

    # Check name map
    if student_name in NAME_MAP:
        for alt_name in NAME_MAP[student_name]:
            matches = df[df[name_col] == alt_name]
            if len(matches) > 0:
                return matches

    # Try partial match (first + last name)
    parts = student_name.split()
    if len(parts) >= 2:
        first, last = parts[0], parts[-1]
        matches = df[df[name_col].str.contains(first, na=False) & df[name_col].str.contains(last, na=False)]
        if len(matches) > 0:
            return matches

    return pd.DataFrame()

# ============================================================
# STEP 2: SCHOOL DAY CALCULATION
# ============================================================
print("\n" + "=" * 80)
print("SCHOOL DAY CALCULATION")
print("=" * 80)

start_date = date(2025, 8, 14)
end_date = date(2026, 1, 23)

# Generate all weekdays
all_days = []
d = start_date
while d <= end_date:
    if d.weekday() < 5:  # Mon-Fri
        all_days.append(d)
    d += timedelta(days=1)

total_weekdays = len(all_days)
print(f"Total weekdays Aug 14 - Jan 23: {total_weekdays}")

# Non-school days (holidays, breaks, MAP testing)
non_school = set()

# MAP Testing weeks (exclude from instructional days)
for d_offset in range(0, 4):  # Aug 19-22
    non_school.add(date(2025, 8, 19) + timedelta(days=d_offset))
for d_offset in range(0, 4):  # Aug 26-29
    non_school.add(date(2025, 8, 26) + timedelta(days=d_offset))

# Labor Day
non_school.add(date(2025, 9, 1))

# Oct Session Break (Oct 6-10)
for d_offset in range(0, 5):
    non_school.add(date(2025, 10, 6) + timedelta(days=d_offset))

# Thanksgiving (Nov 24-28)
for d_offset in range(0, 5):
    non_school.add(date(2025, 11, 24) + timedelta(days=d_offset))

# Dec early dismissal (count Dec 17-18 as half days -> subtract 1 full day equivalent)
half_days = {date(2025, 12, 17), date(2025, 12, 18)}

# Dec 19 is last day of session 2
# Dec 22 - Jan 2: Session Break
for d_offset in range(0, 12):  # Dec 22 to Jan 2
    day = date(2025, 12, 22) + timedelta(days=d_offset)
    if day.weekday() < 5:
        non_school.add(day)

# MLK Day
non_school.add(date(2026, 1, 19))

# Filter out non-school days that aren't weekdays
non_school_weekdays = {d for d in non_school if d.weekday() < 5 and start_date <= d <= end_date}

school_days = [d for d in all_days if d not in non_school_weekdays]
# Subtract 1 for the two half-days (Dec 17-18 = 2 half days = 1 full day equivalent)
effective_school_days = len(school_days) - 1  # subtract 1 for the 2 half days

print(f"Non-school weekdays removed: {len(non_school_weekdays)}")
print(f"  MAP testing: 8 days")
print(f"  Labor Day: 1 day")
print(f"  Oct break: 5 days")
print(f"  Thanksgiving: 5 days")
print(f"  Dec/Jan break: {len([d for d in non_school_weekdays if d >= date(2025, 12, 22)])} days")
print(f"  MLK Day: 1 day")
print(f"  Half days (Dec 17-18): counted as -1 full day")
print(f"School days (before half-day adj): {len(school_days)}")
print(f"Effective instructional days: {effective_school_days}")

EXPECTED_MINUTES = effective_school_days * 25
print(f"Expected reading minutes: {effective_school_days} days × 25 min = {EXPECTED_MINUTES} min")

# ============================================================
# APP CATEGORIZATION
# ============================================================
INSTRUCTION_APPS = {'Alpha Read', 'MobyMax'}
TESTING_APPS = {'Mastery Track', '100 for 100', 'Alpha Tests', '100x100'}
EARLY_LIT_APPS = {'Anton', 'ClearFluency', 'Amplify', 'Mentava', 'Literably',
                   'Lalilo', 'Lexia Core5', 'FastPhonics', 'TeachTales'}
ADMIN_APPS = {'Manual XP Assign', 'Timeback UI', 'TimeBack Dash', 'Manual XP',
              'Acely SAT', 'AlphaLearn'}

def categorize_app(app_name):
    if app_name in INSTRUCTION_APPS:
        return 'Instruction'
    elif app_name in TESTING_APPS:
        return 'Testing'
    elif app_name in EARLY_LIT_APPS:
        return 'Early Lit'
    elif app_name in ADMIN_APPS:
        return 'Admin/Other'
    else:
        return 'Unknown'

# ============================================================
# ANALYSIS 1: TIME ON TASK
# ============================================================
print("\n" + "=" * 80)
print("ANALYSIS 1: TIME ON TASK (Reading Minutes)")
print("=" * 80)

time_results = []
for _, row in deep_dive.iterrows():
    name = row['Student Name']
    if pd.isna(name):
        continue

    mins_df = find_student_in_df(name, minutes_data[minutes_data['subject'] == 'Reading'], 'fullname')
    reading_mins = mins_df['active_minutes (SUM)'].sum() if len(mins_df) > 0 else 0

    growth = row.get('Growth after 1st take (F→W)', np.nan)
    if isinstance(growth, str) and growth.lower() == 'n/a':
        growth = np.nan
    else:
        growth = pd.to_numeric(growth, errors='coerce')

    put_in_time = row.get('Put in expected time? (Session 2)', '')

    time_results.append({
        'Student': name,
        'Grade': row.get('Age Grade', ''),
        'Reading Min': reading_mins,
        'Expected Min': EXPECTED_MINUTES,
        '% Expected': round(reading_mins / EXPECTED_MINUTES * 100, 1) if EXPECTED_MINUTES > 0 else 0,
        'Daily Avg': round(reading_mins / effective_school_days, 1) if effective_school_days > 0 else 0,
        'Put In Time?': put_in_time,
        'Growth F→W': growth
    })

time_df = pd.DataFrame(time_results).sort_values('% Expected', ascending=True)
print(f"\nExpected: {EXPECTED_MINUTES} min ({effective_school_days} days × 25 min/day)")
print(f"{'Student':<25} {'Gr':>3} {'Read Min':>9} {'% Exp':>7} {'Avg/Day':>8} {'PutTime?':>9} {'Growth':>7}")
print("-" * 75)
for _, r in time_df.iterrows():
    growth_str = f"{r['Growth F→W']:.1f}" if pd.notna(r['Growth F→W']) else "n/a"
    print(f"{r['Student']:<25} {r['Grade']:>3} {r['Reading Min']:>9.0f} {r['% Expected']:>6.1f}% {r['Daily Avg']:>7.1f} {str(r['Put In Time?']):>9} {growth_str:>7}")

# Summary stats
print(f"\nSummary:")
print(f"  Students meeting 100% expected: {sum(1 for r in time_results if r['% Expected'] >= 100)}/{len(time_results)}")
print(f"  Students meeting 75% expected: {sum(1 for r in time_results if r['% Expected'] >= 75)}/{len(time_results)}")
print(f"  Students below 50% expected: {sum(1 for r in time_results if r['% Expected'] < 50)}/{len(time_results)}")
avg_pct = np.mean([r['% Expected'] for r in time_results])
print(f"  Average % of expected: {avg_pct:.1f}%")

# ============================================================
# ANALYSIS 2: XP BREAKDOWN BY APP CATEGORY
# ============================================================
print("\n" + "=" * 80)
print("ANALYSIS 2: XP BREAKDOWN BY APP CATEGORY")
print("=" * 80)

xp_results = []
for _, row in deep_dive.iterrows():
    name = row['Student Name']
    if pd.isna(name):
        continue

    student_xp = find_student_in_df(name, xp_data, 'fullname')

    instruction_xp = 0
    testing_xp = 0
    early_lit_xp = 0
    admin_xp = 0
    unknown_xp = 0
    apps_used = []
    app_details = []

    if len(student_xp) > 0:
        for _, xp_row in student_xp.iterrows():
            app = xp_row['app']
            xp = xp_row['xp_earned (SUM)']
            cat = categorize_app(app)
            if xp > 0:
                apps_used.append(app)
                app_details.append(f"{app}:{xp:.0f}")
            if cat == 'Instruction':
                instruction_xp += xp
            elif cat == 'Testing':
                testing_xp += xp
            elif cat == 'Early Lit':
                early_lit_xp += xp
            elif cat == 'Admin/Other':
                admin_xp += xp
            else:
                unknown_xp += xp

    total_xp = instruction_xp + testing_xp + early_lit_xp + admin_xp + unknown_xp

    growth = row.get('Growth after 1st take (F→W)', np.nan)
    if isinstance(growth, str) and growth.lower() == 'n/a':
        growth = np.nan
    else:
        growth = pd.to_numeric(growth, errors='coerce')

    xp_results.append({
        'Student': name,
        'Instruction XP': instruction_xp,
        'Testing XP': testing_xp,
        'Early Lit XP': early_lit_xp,
        'Admin XP': admin_xp,
        'Total XP': total_xp,
        '% Instruction': round(instruction_xp / total_xp * 100, 1) if total_xp > 0 else 0,
        '% Testing': round(testing_xp / total_xp * 100, 1) if total_xp > 0 else 0,
        '% Early Lit': round(early_lit_xp / total_xp * 100, 1) if total_xp > 0 else 0,
        'Growth F→W': growth,
        'App Details': ', '.join(app_details),
        'Flags': []
    })

# Add flags
for r in xp_results:
    if r['% Testing'] > 50:
        r['Flags'].append('OVER-TESTING')
    if r['% Early Lit'] > 10:
        r['Flags'].append('EARLY-LIT-APPS')
    if r['% Instruction'] < 20 and r['Total XP'] > 0:
        r['Flags'].append('NO-INSTRUCTION')
    if r['Total XP'] == 0:
        r['Flags'].append('ZERO-XP')

xp_df = pd.DataFrame(xp_results).sort_values('% Instruction', ascending=True)

print(f"\n{'Student':<25} {'Instr':>6} {'Test':>6} {'ELit':>6} {'Admin':>6} {'Total':>6} {'%Ins':>5} {'%Tst':>5} {'%EL':>5} {'Grwth':>6} {'Flags'}")
print("-" * 110)
for _, r in xp_df.iterrows():
    growth_str = f"{r['Growth F→W']:.1f}" if pd.notna(r['Growth F→W']) else "n/a"
    flags = ','.join(r['Flags']) if r['Flags'] else ''
    print(f"{r['Student']:<25} {r['Instruction XP']:>6.0f} {r['Testing XP']:>6.0f} {r['Early Lit XP']:>6.0f} {r['Admin XP']:>6.0f} {r['Total XP']:>6.0f} {r['% Instruction']:>4.0f}% {r['% Testing']:>4.0f}% {r['% Early Lit']:>4.0f}% {growth_str:>6} {flags}")

print(f"\nApp Details per Student:")
for r in xp_results:
    if r['App Details']:
        print(f"  {r['Student']}: {r['App Details']}")

# ============================================================
# ANALYSIS 3: CORRELATION ANALYSIS
# ============================================================
print("\n" + "=" * 80)
print("ANALYSIS 3: CORRELATION ANALYSIS")
print("=" * 80)

# Merge time and xp data
merged = pd.DataFrame(time_results)
xp_frame = pd.DataFrame(xp_results)
merged = merged.merge(xp_frame[['Student', 'Total XP', '% Instruction', 'Instruction XP', 'Testing XP']], on='Student')
merged = merged.dropna(subset=['Growth F→W'])

from scipy import stats

if len(merged) >= 3:
    # Minutes vs Growth
    r_minutes, p_minutes = stats.pearsonr(merged['Reading Min'], merged['Growth F→W'])
    rho_minutes, p_rho_min = stats.spearmanr(merged['Reading Min'], merged['Growth F→W'])
    print(f"\nReading Minutes vs Growth (N={len(merged)}):")
    print(f"  Pearson r = {r_minutes:.3f} (p = {p_minutes:.3f})")
    print(f"  Spearman ρ = {rho_minutes:.3f} (p = {p_rho_min:.3f})")

    # Total XP vs Growth
    r_xp, p_xp = stats.pearsonr(merged['Total XP'], merged['Growth F→W'])
    rho_xp, p_rho_xp = stats.spearmanr(merged['Total XP'], merged['Growth F→W'])
    print(f"\nTotal XP vs Growth:")
    print(f"  Pearson r = {r_xp:.3f} (p = {p_xp:.3f})")
    print(f"  Spearman ρ = {rho_xp:.3f} (p = {p_rho_xp:.3f})")

    # Instruction XP % vs Growth
    r_inst, p_inst = stats.pearsonr(merged['% Instruction'], merged['Growth F→W'])
    rho_inst, p_rho_inst = stats.spearmanr(merged['% Instruction'], merged['Growth F→W'])
    print(f"\n% Instruction XP vs Growth:")
    print(f"  Pearson r = {r_inst:.3f} (p = {p_inst:.3f})")
    print(f"  Spearman ρ = {rho_inst:.3f} (p = {p_rho_inst:.3f})")

    # Instruction XP (absolute) vs Growth
    r_inst_abs, p_inst_abs = stats.pearsonr(merged['Instruction XP'], merged['Growth F→W'])
    print(f"\nInstruction XP (absolute) vs Growth:")
    print(f"  Pearson r = {r_inst_abs:.3f} (p = {p_inst_abs:.3f})")

    # Testing XP vs Growth
    r_test, p_test = stats.pearsonr(merged['Testing XP'], merged['Growth F→W'])
    print(f"\nTesting XP vs Growth:")
    print(f"  Pearson r = {r_test:.3f} (p = {p_test:.3f})")

    print(f"\nNote: N={len(merged)} -- small sample, interpret cautiously.")
else:
    print("Not enough data points for correlation analysis.")

# ============================================================
# ANALYSIS 4: GAMING / WASTE / MISALLOCATION DETECTION
# ============================================================
print("\n" + "=" * 80)
print("ANALYSIS 4: GAMING / WASTE / MISALLOCATION DETECTION")
print("=" * 80)

for i, r in enumerate(xp_results):
    student = r['Student']
    time_r = next((t for t in time_results if t['Student'] == student), None)
    reading_mins = time_r['Reading Min'] if time_r else 0

    flags = []

    # Over-testing
    if r['% Testing'] > 60:
        flags.append(f"OVER-TESTING: {r['% Testing']:.0f}% of XP from testing apps ({r['Testing XP']:.0f} XP)")

    # Early Lit apps (wrong for G3+)
    if r['% Early Lit'] > 10:
        flags.append(f"EARLY-LIT APPS: {r['% Early Lit']:.0f}% of XP from below-G3 apps ({r['Early Lit XP']:.0f} XP)")

    # No instruction
    if r['Instruction XP'] == 0 and r['Total XP'] > 0:
        flags.append(f"NO INSTRUCTION: Zero XP from Alpha Read or MobyMax")
    elif r['% Instruction'] < 20 and r['Total XP'] > 100:
        flags.append(f"LOW INSTRUCTION: Only {r['% Instruction']:.0f}% from instruction apps ({r['Instruction XP']:.0f} XP)")

    # XP efficiency (gaming detection)
    if reading_mins > 0 and r['Total XP'] > 0:
        xp_per_min = r['Total XP'] / reading_mins
        if xp_per_min > 3:
            flags.append(f"HIGH XP/MIN: {xp_per_min:.1f} XP/min (possible gaming)")

    # Time wasting: high minutes but very low XP
    if reading_mins > EXPECTED_MINUTES * 0.8 and r['Total XP'] < 100:
        flags.append(f"TIME WASTING: {reading_mins:.0f} min but only {r['Total XP']:.0f} XP")

    if flags:
        growth_str = f"{r['Growth F→W']:.1f}" if pd.notna(r['Growth F→W']) else "n/a"
        print(f"\n{student} (Growth: {growth_str}):")
        for f in flags:
            print(f"  ⚠ {f}")

    xp_results[i]['All Flags'] = flags

# Students with no flags
no_flag_students = [r['Student'] for r in xp_results if not r.get('All Flags', [])]
if no_flag_students:
    print(f"\nStudents with no flags: {', '.join(no_flag_students)}")

# ============================================================
# ANALYSIS 5: COMMENTS CROSS-REFERENCE
# ============================================================
print("\n" + "=" * 80)
print("ANALYSIS 5: QUALITATIVE COMMENTS + QUANTITATIVE DATA")
print("=" * 80)

for _, row in deep_dive.iterrows():
    name = row['Student Name']
    if pd.isna(name):
        continue

    comments = row.get('Comments', '')
    if pd.isna(comments) or str(comments).strip() == '':
        continue

    # Find matching time and XP data
    time_r = next((t for t in time_results if t['Student'] == name), None)
    xp_r = next((x for x in xp_results if x['Student'] == name), None)

    growth = row.get('Growth after 1st take (F→W)', 'n/a')

    print(f"\n{'─' * 60}")
    print(f"STUDENT: {name} | Grade: {row.get('Age Grade', '?')} | Growth F→W: {growth}")
    if time_r:
        print(f"  Reading Min: {time_r['Reading Min']:.0f} ({time_r['% Expected']:.0f}% of expected) | Daily Avg: {time_r['Daily Avg']:.1f} min")
    if xp_r:
        print(f"  XP: Instruction={xp_r['Instruction XP']:.0f}, Testing={xp_r['Testing XP']:.0f}, Early Lit={xp_r['Early Lit XP']:.0f}, Total={xp_r['Total XP']:.0f}")
        print(f"  Apps: {xp_r['App Details']}")
    print(f"  COMMENT: {comments}")

# ============================================================
# ANALYSIS 6: PEER COMPARISON
# ============================================================
print("\n" + "=" * 80)
print("ANALYSIS 6: PEER COMPARISON")
print("=" * 80)

# School-wide reading minutes
all_reading_mins = minutes_data[minutes_data['subject'] == 'Reading'].groupby('fullname')['active_minutes (SUM)'].sum()
# School-wide reading XP
all_reading_xp = xp_data.groupby('fullname')['xp_earned (SUM)'].sum()

print(f"\nSchool-wide Reading Minutes (N={len(all_reading_mins)}):")
print(f"  Mean: {all_reading_mins.mean():.0f} | Median: {all_reading_mins.median():.0f}")
print(f"  P25: {all_reading_mins.quantile(0.25):.0f} | P75: {all_reading_mins.quantile(0.75):.0f} | P90: {all_reading_mins.quantile(0.90):.0f}")

print(f"\nSchool-wide Reading XP (N={len(all_reading_xp)}):")
print(f"  Mean: {all_reading_xp.mean():.0f} | Median: {all_reading_xp.median():.0f}")
print(f"  P25: {all_reading_xp.quantile(0.25):.0f} | P75: {all_reading_xp.quantile(0.75):.0f} | P90: {all_reading_xp.quantile(0.90):.0f}")

print(f"\n{'Student':<25} {'Read Min':>9} {'Min Pctl':>9} {'Total XP':>9} {'XP Pctl':>8} {'Growth':>7}")
print("-" * 72)

for r_time, r_xp in zip(
    sorted(time_results, key=lambda x: x['Growth F→W'] if pd.notna(x['Growth F→W']) else 999),
    sorted(xp_results, key=lambda x: x['Growth F→W'] if pd.notna(x['Growth F→W']) else 999)
):
    name = r_time['Student']
    r_xp_match = next((x for x in xp_results if x['Student'] == name), None)

    reading_mins = r_time['Reading Min']
    total_xp = r_xp_match['Total XP'] if r_xp_match else 0

    min_pctl = (all_reading_mins < reading_mins).sum() / len(all_reading_mins) * 100
    xp_pctl = (all_reading_xp < total_xp).sum() / len(all_reading_xp) * 100

    growth = r_time['Growth F→W']
    growth_str = f"{growth:.1f}" if pd.notna(growth) else "n/a"

    print(f"{name:<25} {reading_mins:>9.0f} {min_pctl:>8.0f}% {total_xp:>9.0f} {xp_pctl:>7.0f}% {growth_str:>7}")

# ============================================================
# ANALYSIS 8: TEST HISTORY DEEP DIVE
# ============================================================
print("\n" + "=" * 80)
print("ANALYSIS 8: TEST HISTORY DEEP DIVE")
print("=" * 80)

test_results = []
for _, row in deep_dive.iterrows():
    name = row['Student Name']
    if pd.isna(name):
        continue

    student_tests = find_student_in_df(name, test_history[test_history['Subject'] == 'Reading'], 'Student')

    if len(student_tests) == 0:
        test_results.append({
            'Student': name,
            'Total Tests': 0,
            'Effective Tests': 0,
            'Effective Rate': 0,
            'Avg Accuracy': 0,
            'Low Accuracy Tests': 0,
            'Max Attempts': 0,
            'Grades Tested': '',
            'Doom Loop Grades': [],
            'Tests/Week': 0,
            'Date Range': 'N/A',
            'Test Summary': 'NO TEST HISTORY FOUND'
        })
        continue

    total_tests = len(student_tests)
    effective_tests = student_tests['Effective Test?'].sum()
    effective_rate = effective_tests / total_tests * 100 if total_tests > 0 else 0
    avg_accuracy = student_tests['Accuracy'].mean()
    low_accuracy = (student_tests['Accuracy'] < 70).sum()

    # Grade levels tested
    grades_tested = sorted(student_tests['Test Grade'].unique())

    # Max attempts on any single grade
    attempts_by_grade = student_tests.groupby('Test Grade')['Test Attempt #'].max()
    max_attempts = attempts_by_grade.max() if len(attempts_by_grade) > 0 else 0
    doom_loop_grades = attempts_by_grade[attempts_by_grade >= 3].index.tolist()

    # Date range
    date_range = f"{student_tests['Submission Date'].min().strftime('%Y-%m-%d')} to {student_tests['Submission Date'].max().strftime('%Y-%m-%d')}"

    # Tests per week
    if len(student_tests) > 1:
        date_span = (student_tests['Submission Date'].max() - student_tests['Submission Date'].min()).days / 7
        tests_per_week = total_tests / date_span if date_span > 0 else total_tests
    else:
        tests_per_week = 0

    summary_parts = []
    if doom_loop_grades:
        summary_parts.append(f"DOOM LOOP grades: {doom_loop_grades}")
    if low_accuracy > 0:
        summary_parts.append(f"{low_accuracy} low-accuracy tests (<70%)")
    if effective_rate < 50:
        summary_parts.append(f"Low effective rate: {effective_rate:.0f}%")

    test_results.append({
        'Student': name,
        'Total Tests': total_tests,
        'Effective Tests': effective_tests,
        'Effective Rate': effective_rate,
        'Avg Accuracy': avg_accuracy,
        'Low Accuracy Tests': low_accuracy,
        'Max Attempts': max_attempts,
        'Grades Tested': str(grades_tested),
        'Doom Loop Grades': doom_loop_grades,
        'Tests/Week': tests_per_week,
        'Date Range': date_range,
        'Test Summary': '; '.join(summary_parts) if summary_parts else 'Normal'
    })

print(f"\n{'Student':<25} {'Tests':>6} {'Effect':>7} {'Eff%':>5} {'Avg Acc':>8} {'Low Acc':>8} {'Max Att':>8} {'Tst/Wk':>7}")
print("-" * 85)
for r in sorted(test_results, key=lambda x: -x['Total Tests']):
    print(f"{r['Student']:<25} {r['Total Tests']:>6} {r['Effective Tests']:>7.0f} {r['Effective Rate']:>4.0f}% {r['Avg Accuracy']:>7.1f} {r['Low Accuracy Tests']:>8} {r['Max Attempts']:>8.0f} {r['Tests/Week']:>6.1f}")
    if r['Test Summary'] != 'Normal' and r['Test Summary'] != 'NO TEST HISTORY FOUND':
        print(f"  ⚠ {r['Test Summary']}")

print(f"\nDetailed Test History per Student:")
for r in test_results:
    if r['Total Tests'] > 0:
        print(f"\n  {r['Student']}: {r['Total Tests']} tests ({r['Date Range']})")
        print(f"    Grades tested: {r['Grades Tested']}")
        if r.get('Doom Loop Grades'):
            print(f"    ⚠ DOOM LOOP on grades: {r['Doom Loop Grades']}")

# ============================================================
# ANALYSIS 9: YEAR-OVER-YEAR GROWTH
# ============================================================
print("\n" + "=" * 80)
print("ANALYSIS 9: YEAR-OVER-YEAR GROWTH (Spring 2025 → Fall 2025 → Winter 2026)")
print("=" * 80)

yoy_results = []
for _, row in deep_dive.iterrows():
    name = row['Student Name']
    if pd.isna(name):
        continue

    # Get spring MAP score
    spring_score = find_student_in_df(name, spring_map_reading, 'Student')
    spring_rit = spring_score['Spring 2425 RIT'].values[0] if len(spring_score) > 0 else np.nan

    # Get fall and winter scores from deep dive
    fall_rit = pd.to_numeric(row.get('previous RIT Score (F)', np.nan), errors='coerce')
    winter_rit = pd.to_numeric(row.get('1st take RIT Score (W)', np.nan), errors='coerce')

    summer_slide = fall_rit - spring_rit if pd.notna(fall_rit) and pd.notna(spring_rit) else np.nan
    spring_to_winter = winter_rit - spring_rit if pd.notna(winter_rit) and pd.notna(spring_rit) else np.nan
    fall_to_winter = winter_rit - fall_rit if pd.notna(winter_rit) and pd.notna(fall_rit) else np.nan

    yoy_results.append({
        'Student': name,
        'Grade': row.get('Age Grade', ''),
        'Spring 25 RIT': spring_rit,
        'Fall 25 RIT': fall_rit,
        'Winter 26 RIT': winter_rit,
        'Summer Slide': summer_slide,
        'Spring→Winter': spring_to_winter,
        'Fall→Winter': fall_to_winter
    })

print(f"\n{'Student':<25} {'Gr':>3} {'Spr25':>6} {'Fall25':>7} {'Win26':>6} {'Summer':>7} {'Spr→Win':>8} {'Fall→Win':>9}")
print("-" * 80)
for r in sorted(yoy_results, key=lambda x: x['Fall→Winter'] if pd.notna(x['Fall→Winter']) else 999):
    spr = f"{r['Spring 25 RIT']:.0f}" if pd.notna(r['Spring 25 RIT']) else "n/a"
    fall = f"{r['Fall 25 RIT']:.0f}" if pd.notna(r['Fall 25 RIT']) else "n/a"
    win = f"{r['Winter 26 RIT']:.0f}" if pd.notna(r['Winter 26 RIT']) else "n/a"
    summer = f"{r['Summer Slide']:+.0f}" if pd.notna(r['Summer Slide']) else "n/a"
    spr_win = f"{r['Spring→Winter']:+.0f}" if pd.notna(r['Spring→Winter']) else "n/a"
    f_w = f"{r['Fall→Winter']:+.0f}" if pd.notna(r['Fall→Winter']) else "n/a"
    print(f"{r['Student']:<25} {r['Grade']:>3} {spr:>6} {fall:>7} {win:>6} {summer:>7} {spr_win:>8} {f_w:>9}")

# Summer slide summary
slides = [r['Summer Slide'] for r in yoy_results if pd.notna(r['Summer Slide'])]
if slides:
    print(f"\nSummer Slide Summary (Spring → Fall):")
    print(f"  Students with data: {len(slides)}/{len(yoy_results)}")
    print(f"  Average slide: {np.mean(slides):+.1f} RIT points")
    print(f"  Students who regressed: {sum(1 for s in slides if s < 0)}/{len(slides)}")
    print(f"  Students who grew: {sum(1 for s in slides if s > 0)}/{len(slides)}")

# ============================================================
# ANALYSIS 7: STUDENT CLUSTERING
# ============================================================
print("\n" + "=" * 80)
print("ANALYSIS 7: STUDENT CLUSTERING & RECOMMENDATIONS")
print("=" * 80)

clusters = defaultdict(list)

for i, name in enumerate([r['Student'] for r in time_results]):
    time_r = time_results[i]
    xp_r = next((x for x in xp_results if x['Student'] == name), None)
    test_r = next((t for t in test_results if t['Student'] == name), None)

    assigned = False
    student_clusters = []

    # Low Effort
    if time_r['% Expected'] < 50:
        student_clusters.append('Low Effort')

    # Over-Testing
    if xp_r and xp_r['% Testing'] > 50:
        student_clusters.append('Over-Testing')

    # Wrong Apps (Early Lit) -- but check if justified
    if xp_r and xp_r['% Early Lit'] > 10:
        student_clusters.append('Wrong Apps (Early Lit)')

    # No Instruction
    if xp_r and xp_r['Instruction XP'] == 0 and xp_r['Total XP'] > 0:
        student_clusters.append('No Instruction')

    # Test Doom Loop
    if test_r and test_r.get('Doom Loop Grades'):
        student_clusters.append('Test Doom Loop')

    # Adequate Effort, Possible Bad Test
    dd_row = deep_dive[deep_dive['Student Name'] == name].iloc[0] if len(deep_dive[deep_dive['Student Name'] == name]) > 0 else None
    if dd_row is not None:
        rushed = dd_row.get('Rushed MAP test?', '')
        if time_r['% Expected'] >= 75 and (str(rushed).lower() == 'yes' or str(rushed).lower() == 'true'):
            student_clusters.append('Adequate Effort, Bad Test')

    # Quality Issue (good time, poor results, no other flags)
    if not student_clusters and time_r['% Expected'] >= 75:
        student_clusters.append('Quality Issue')

    # Default
    if not student_clusters:
        student_clusters.append('Mixed/Unclear')

    for c in student_clusters:
        clusters[c].append(name)

print(f"\n{'Cluster':<30} {'Count':>6} Students")
print("-" * 80)
for cluster_name in ['Low Effort', 'Over-Testing', 'Wrong Apps (Early Lit)', 'No Instruction',
                      'Test Doom Loop', 'Adequate Effort, Bad Test', 'Quality Issue', 'Mixed/Unclear']:
    if cluster_name in clusters:
        students = clusters[cluster_name]
        print(f"{cluster_name:<30} {len(students):>6} {', '.join(students)}")

print(f"\nRecommendations by Cluster:")
recommendations = {
    'Low Effort': 'Increase time on task. Ensure 25 min/day minimum in reading. Monitor attendance and engagement.',
    'Over-Testing': 'Redirect from testing to instruction apps (Alpha Read, MobyMax). Testing is NOT learning.',
    'Wrong Apps (Early Lit)': 'Verify if student has passed G3 tests. If yes, move to Alpha Read + MobyMax immediately.',
    'No Instruction': 'Assign to Alpha Read and MobyMax. These students have zero learning app usage.',
    'Test Doom Loop': 'Break the cycle. Stop retesting and return to instruction. Build skills before testing again.',
    'Adequate Effort, Bad Test': 'Retest under controlled conditions. Student may have rushed or had a bad day.',
    'Quality Issue': 'Investigate engagement quality. Good time but poor outcomes may indicate distraction or ineffective app usage.',
    'Mixed/Unclear': 'Individual review needed. Multiple contributing factors.'
}
for cluster_name, rec in recommendations.items():
    if cluster_name in clusters:
        print(f"\n  {cluster_name}: {rec}")

# ============================================================
# SUMMARY DASHBOARD
# ============================================================
print("\n" + "=" * 80)
print("SUMMARY DASHBOARD (sorted by growth, worst first)")
print("=" * 80)

# Build comprehensive summary
summary = []
for _, row in deep_dive.iterrows():
    name = row['Student Name']
    if pd.isna(name):
        continue

    time_r = next((t for t in time_results if t['Student'] == name), None)
    xp_r = next((x for x in xp_results if x['Student'] == name), None)
    test_r = next((t for t in test_results if t['Student'] == name), None)
    yoy_r = next((y for y in yoy_results if y['Student'] == name), None)

    growth = row.get('Growth after 1st take (F→W)', np.nan)
    if isinstance(growth, str) and growth.lower() == 'n/a':
        growth = np.nan
    else:
        growth = pd.to_numeric(growth, errors='coerce')

    # Find clusters
    student_clusters = []
    for c, students in clusters.items():
        if name in students:
            student_clusters.append(c)

    summary.append({
        'Student': name,
        'Grade': row.get('Age Grade', ''),
        'Spring25': yoy_r['Spring 25 RIT'] if yoy_r else np.nan,
        'Fall25': yoy_r['Fall 25 RIT'] if yoy_r else np.nan,
        'Winter26': yoy_r['Winter 26 RIT'] if yoy_r else np.nan,
        'Growth': growth,
        'Summer Slide': yoy_r['Summer Slide'] if yoy_r else np.nan,
        'Read Min': time_r['Reading Min'] if time_r else 0,
        '% Expected': time_r['% Expected'] if time_r else 0,
        'Instr XP': xp_r['Instruction XP'] if xp_r else 0,
        'Test XP': xp_r['Testing XP'] if xp_r else 0,
        'ELit XP': xp_r['Early Lit XP'] if xp_r else 0,
        '% Instr': xp_r['% Instruction'] if xp_r else 0,
        'Tests': test_r['Total Tests'] if test_r else 0,
        'Eff%': test_r['Effective Rate'] if test_r else 0,
        'Cluster': ' | '.join(student_clusters),
    })

summary_df = pd.DataFrame(summary).sort_values('Growth', ascending=True)

print(f"\n{'Student':<22} {'Gr':>2} {'Spr':>4} {'Fal':>4} {'Win':>4} {'Grw':>5} {'Slid':>5} {'RdMn':>5} {'%Exp':>5} {'InXP':>5} {'TsXP':>5} {'ELXP':>5} {'%In':>4} {'Tst':>4} {'Ef%':>4} Cluster")
print("-" * 130)
for _, r in summary_df.iterrows():
    spr = f"{r['Spring25']:.0f}" if pd.notna(r['Spring25']) else "-"
    fall = f"{r['Fall25']:.0f}" if pd.notna(r['Fall25']) else "-"
    win = f"{r['Winter26']:.0f}" if pd.notna(r['Winter26']) else "-"
    grw = f"{r['Growth']:.0f}" if pd.notna(r['Growth']) else "-"
    slide = f"{r['Summer Slide']:+.0f}" if pd.notna(r['Summer Slide']) else "-"
    print(f"{r['Student']:<22} {r['Grade']:>2} {spr:>4} {fall:>4} {win:>4} {grw:>5} {slide:>5} {r['Read Min']:>5.0f} {r['% Expected']:>4.0f}% {r['Instr XP']:>5.0f} {r['Test XP']:>5.0f} {r['ELit XP']:>5.0f} {r['% Instr']:>3.0f}% {r['Tests']:>4} {r['Eff%']:>3.0f}% {r['Cluster']}")

# ============================================================
# EXECUTIVE SUMMARY
# ============================================================
print("\n" + "=" * 80)
print("EXECUTIVE SUMMARY")
print("=" * 80)

# Key stats
total_students = len(time_results)
avg_growth = np.nanmean([r['Growth F→W'] for r in time_results])
negative_growth = sum(1 for r in time_results if pd.notna(r['Growth F→W']) and r['Growth F→W'] < 0)
zero_growth = sum(1 for r in time_results if pd.notna(r['Growth F→W']) and r['Growth F→W'] == 0)
positive_growth = sum(1 for r in time_results if pd.notna(r['Growth F→W']) and r['Growth F→W'] > 0)

print(f"\n1. OVERVIEW:")
print(f"   {total_students} students analyzed | Average growth: {avg_growth:+.1f} RIT points")
print(f"   Negative growth: {negative_growth} | Zero growth: {zero_growth} | Positive growth (but <2x): {positive_growth}")

print(f"\n2. TIME ON TASK:")
meeting_time = sum(1 for r in time_results if r['% Expected'] >= 100)
below_75 = sum(1 for r in time_results if r['% Expected'] < 75)
print(f"   {meeting_time}/{total_students} students met 100% expected reading minutes")
print(f"   {below_75}/{total_students} students were below 75% of expected minutes")
print(f"   Average daily reading: {np.mean([r['Daily Avg'] for r in time_results]):.1f} min (target: 25 min)")

print(f"\n3. APP USAGE:")
no_instruction = sum(1 for r in xp_results if r['Instruction XP'] == 0 and r['Total XP'] > 0)
over_testing = sum(1 for r in xp_results if r['% Testing'] > 50)
early_lit = sum(1 for r in xp_results if r['% Early Lit'] > 10)
print(f"   {no_instruction}/{total_students} students had ZERO instruction app (Alpha Read/MobyMax) XP")
print(f"   {over_testing}/{total_students} students spent >50% of XP on testing (not learning)")
print(f"   {early_lit}/{total_students} students had >10% of XP from early literacy apps")

print(f"\n4. KEY FINDING - MINUTES DON'T GUARANTEE GROWTH:")
high_min_neg_growth = sum(1 for r in time_results if r['% Expected'] >= 100 and pd.notna(r['Growth F→W']) and r['Growth F→W'] < 0)
print(f"   {high_min_neg_growth} students met 100% time but still had NEGATIVE growth")
print(f"   This suggests the problem is WHAT they're doing, not HOW MUCH time they spend")

print(f"\n5. CLUSTER DISTRIBUTION:")
for cluster_name in ['Low Effort', 'Over-Testing', 'Wrong Apps (Early Lit)', 'No Instruction',
                      'Test Doom Loop', 'Adequate Effort, Bad Test', 'Quality Issue', 'Mixed/Unclear']:
    if cluster_name in clusters:
        print(f"   {cluster_name}: {len(clusters[cluster_name])} students")

print(f"\n6. SUMMER SLIDE:")
slides = [r['Summer Slide'] for r in yoy_results if pd.notna(r['Summer Slide'])]
if slides:
    regressed = sum(1 for s in slides if s < 0)
    print(f"   {len(slides)} students had spring scores available")
    print(f"   {regressed}/{len(slides)} regressed over summer (avg slide: {np.mean([s for s in slides if s < 0]):+.1f} if negative)")

print("\n" + "=" * 80)
print("END OF ANALYSIS")
print("=" * 80)

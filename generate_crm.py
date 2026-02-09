#!/usr/bin/env python3
"""
Reading 3+ Results: Generate dashboard + individual student profile pages
from Winter 25-26 MAP Analysis + daily metrics + test results.

Covers all ~458 Reading students across all campuses.
Output: docs/crm/index.html + docs/crm/students/*.html
"""

import pandas as pd
import numpy as np
import json
import re
import os
from datetime import date, timedelta
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# CONSTANTS
# ============================================================
DATA_DIR = "/Users/alexandra/Documents/Claude"
OUT_DIR = os.path.join(DATA_DIR, "docs", "crm")
STUDENTS_DIR = os.path.join(OUT_DIR, "students")
JSON_FILE = os.path.join(DATA_DIR, "crm_data.json")

# School calendar
START_DATE = date(2025, 8, 14)
END_DATE = date(2026, 1, 23)
EXPECTED_DAILY_MINUTES = 25
PASS_THRESHOLD = 89.5  # 89.5% rounds up to 90%

# App categorization
INSTRUCTION_APPS = {'MobyMax'}
PRACTICE_APPS = {'Alpha Read'}
TESTING_APPS = {'Mastery Track', '100 for 100', 'Alpha Tests', '100x100', '100 for 100'}
EARLY_LIT_APPS = {'Anton', 'ClearFluency', 'Clear Fluency', 'Amplify', 'Mentava',
                   'Literably', 'Lalilo', 'Lexia Core5', 'FastPhonics', 'TeachTales',
                   'AlphaLiteracy'}
ADMIN_APPS = {'Manual XP Assign', 'Manual XP', 'Timeback UI', 'TimeBack Dash',
              'Acely SAT', 'AlphaLearn', 'Alpha Timeback', 'Timeback Learn'}


def categorize_app(app_name):
    if app_name in INSTRUCTION_APPS:
        return 'Instruction'
    elif app_name in PRACTICE_APPS:
        return 'Practice'
    elif app_name in TESTING_APPS:
        return 'Testing'
    elif app_name in EARLY_LIT_APPS:
        return 'Early Lit'
    elif app_name in ADMIN_APPS:
        return 'Admin/Other'
    else:
        return 'Admin/Other'


# ============================================================
# SCHOOL DAY CALCULATION
# ============================================================
def compute_school_days():
    """Compute effective school days and list of school dates."""
    all_days = []
    d = START_DATE
    while d <= END_DATE:
        if d.weekday() < 5:
            all_days.append(d)
        d += timedelta(days=1)

    non_school = set()
    # MAP testing weeks
    for d_offset in range(0, 4):
        non_school.add(date(2025, 8, 19) + timedelta(days=d_offset))
    for d_offset in range(0, 4):
        non_school.add(date(2025, 8, 26) + timedelta(days=d_offset))
    # Labor Day
    non_school.add(date(2025, 9, 1))
    # Oct Session Break
    for d_offset in range(0, 5):
        non_school.add(date(2025, 10, 6) + timedelta(days=d_offset))
    # Thanksgiving
    for d_offset in range(0, 5):
        non_school.add(date(2025, 11, 24) + timedelta(days=d_offset))
    # Dec/Jan break
    for d_offset in range(0, 12):
        day = date(2025, 12, 22) + timedelta(days=d_offset)
        if day.weekday() < 5:
            non_school.add(day)
    # MLK Day
    non_school.add(date(2026, 1, 19))

    non_school_weekdays = {d for d in non_school if d.weekday() < 5 and START_DATE <= d <= END_DATE}
    school_days = [d for d in all_days if d not in non_school_weekdays]
    # Subtract 1 for two half-days (Dec 17-18)
    effective_days = len(school_days) - 1
    expected_minutes = effective_days * EXPECTED_DAILY_MINUTES
    return effective_days, expected_minutes, school_days


# ============================================================
# DATA LOADING
# ============================================================
def load_map_analysis():
    """Load Winter 25-26 MAP Analysis, filter to Reading."""
    df = pd.read_csv(f"{DATA_DIR}/Winter 25-26 MAP Analysis 2025-02-09.csv", encoding='utf-8')
    # Filter to Reading
    df = df[df['Subject'] == 'Reading'].copy()
    # Exclude Early Lit students (Early Reading program, not G3+)
    df = df[~df['Comments'].str.contains('Early Lit', case=False, na=False)]
    # Note: HS students kept but differentiated by reading level (≤G8 vs G9+)
    df['Email'] = df['Email'].str.strip().str.lower()
    # Clean numeric columns
    for col in ['RIT', 'HMG', 'Age Grade', 'previous RIT Score (F)',
                'projected RIT score (W)', 'Alpha projected growth (F→W)',
                '1st take RIT Score (W)', 'Effective Grades Mastered 25-26']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    # Growth columns
    for col in ['Growth after 1st take (F→W)', 'Growth after 1st take (W→W)']:
        if col in df.columns:
            df[col] = df[col].replace('n/a', np.nan).replace('', np.nan)
            df[col] = pd.to_numeric(df[col], errors='coerce')
    print(f"MAP Analysis: {len(df)} Reading students loaded")
    return df


def load_daily_metrics():
    """Load daily metrics CSV, filter out test accounts."""
    df = pd.read_csv(
        f"{DATA_DIR}/data daily metrics/Daily_Metrics_by_Student_2025-08-13 → 2026-02-25.csv",
        encoding='utf-8-sig'
    )
    df['email'] = df['email'].str.strip().str.lower()
    # Filter out test accounts
    df = df[~df['email'].str.startswith('_test_')].copy()
    df['date'] = pd.to_datetime(df['date'])
    for col in ['Accuracy (%)', 'Correct Questions', 'Total Questions',
                'Mastered Lessons', 'XP Earned', 'Active Minutes',
                'Inactive Minutes', 'Waste Minutes']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    print(f"Daily Metrics: {len(df)} rows, {df['email'].nunique()} unique students")
    return df


def load_reading_results():
    """Load reading test results."""
    df = pd.read_csv(
        f"{DATA_DIR}/data test results/reading-results-2026-02-05.csv",
        encoding='utf-8-sig'
    )
    df['student_email'] = df['student_email'].str.strip().str.lower()
    df['score'] = pd.to_numeric(df['score'], errors='coerce')
    df['xp'] = pd.to_numeric(df['xp'], errors='coerce').fillna(0)
    df['time_spent_seconds'] = pd.to_numeric(df['time_spent_seconds'], errors='coerce').fillna(0)
    df['test_grade'] = pd.to_numeric(df['test_grade'], errors='coerce')
    df['score_date_utc'] = pd.to_datetime(df['score_date_utc'], format='mixed', errors='coerce')
    # Filter to Reading only
    df = df[df['subject'] == 'Reading'].copy()
    # Filter to current school year only (Aug 14, 2025+)
    pre_filter = len(df)
    df = df[df['score_date_utc'] >= '2025-08-14'].copy()
    print(f"Reading Results: {len(df)} rows (filtered from {pre_filter}), {df['student_email'].nunique()} unique students")
    return df


def load_spring_map():
    """Load Spring MAP scores, filter to Reading."""
    df = pd.read_csv(f"{DATA_DIR}/Last Years Spring MAP Scores.csv", encoding='utf-8')
    df = df[df['Subject'] == 'Reading'].copy()
    df['Spring 2425 RIT'] = pd.to_numeric(df['Spring 2425 RIT'], errors='coerce')
    df['Student'] = df['Student'].str.strip()
    print(f"Spring MAP: {len(df)} reading scores loaded")
    return df


# ============================================================
# NAME / SLUG UTILITIES
# ============================================================
def anonymize_name(full_name):
    """Convert 'Love Lalla-Pagan' to 'Love L.'"""
    parts = full_name.strip().split()
    if len(parts) == 1:
        return parts[0]
    first = parts[0]
    last_initial = parts[-1][0].upper()
    return f"{first} {last_initial}."


def make_base_slug(anon_name):
    """Create URL-safe slug from anonymized name."""
    s = anon_name.lower().replace("ö", "oe").replace(" ", "_").replace(".", "")
    s = re.sub(r'[^a-z0-9_-]', '', s)
    return s


def resolve_slugs(students):
    """Two-pass slug resolution: detect collisions, append last name for dupes."""
    # Pass 1: compute base slugs
    base_map = defaultdict(list)
    for s in students:
        base = make_base_slug(s['name'])
        base_map[base].append(s)

    # Pass 2: resolve collisions
    for base, group in base_map.items():
        if len(group) == 1:
            group[0]['slug'] = base
        else:
            for s in group:
                last_name = s['original_name'].split()[-1].lower()
                last_clean = re.sub(r'[^a-z0-9]', '', last_name)
                s['slug'] = f"{base}_{last_clean}"


# ============================================================
# PER-STUDENT METRIC COMPUTATION
# ============================================================
def compute_student_metrics(row, daily_data, test_data, spring_rit,
                            effective_days, expected_minutes, school_day_dates):
    """Compute all metrics for one student."""
    email = row['Email']
    name = row['Student Name']
    anon = anonymize_name(name)

    # --- MAP Analysis fields ---
    fall_rit = row.get('previous RIT Score (F)', np.nan)
    winter_rit = row.get('1st take RIT Score (W)', np.nan)
    growth_fw = row.get('Growth after 1st take (F→W)', np.nan)
    growth_ww = row.get('Growth after 1st take (W→W)', np.nan)
    hmg = row.get('HMG', np.nan)
    rit = row.get('RIT', np.nan)
    age_grade = row.get('Age Grade', np.nan)
    projected_rit = row.get('projected RIT score (W)', np.nan)
    alpha_projected = row.get('Alpha projected growth (F→W)', np.nan)
    eff_mastered = row.get('Effective Grades Mastered 25-26', 0)
    if pd.isna(eff_mastered):
        eff_mastered = 0
    current_pred = row.get('Current Grade Prediction', '')
    early_lit = str(row.get('Early Lit', '')).strip().upper()
    campus = row.get('Campus', '')
    level = row.get('Level', '')
    # HS reading level differentiation (initial, will be recalculated after HMG fallback)
    hs_reading_category = ''
    level_display = level
    deep_dive = str(row.get('Deep Dive', ''))
    comments = str(row.get('Comments', ''))
    if comments == 'nan':
        comments = ''
    rushed_map = str(row.get('Rushed MAP test?', ''))
    retake_recommended = str(row.get('Retake Recommended?', ''))
    was_pred_valid = str(row.get('Was prediction valid?', ''))
    put_time = str(row.get('Put in expected time? (Session 2)', ''))
    earned_xp_flag = str(row.get('Earned expected XP? (Session 2)', ''))
    accuracy_flag = str(row.get('Ave accuracy >80%? (Session 2)', ''))
    mastered_1 = str(row.get('Mastered at least 1 effective grade test?', ''))

    # --- Daily metrics aggregation ---
    has_daily = len(daily_data) > 0
    total_active = daily_data['Active Minutes'].sum() if has_daily else 0
    total_inactive = daily_data['Inactive Minutes'].sum() if has_daily else 0
    total_waste = daily_data['Waste Minutes'].sum() if has_daily else 0
    total_xp = daily_data['XP Earned'].sum() if has_daily else 0
    pct_expected = round(total_active / expected_minutes * 100, 1) if expected_minutes > 0 else 0
    daily_avg = round(total_active / effective_days, 1) if effective_days > 0 else 0

    # Per-app breakdown
    app_breakdown = []
    instr_xp = 0
    practice_xp = 0
    testing_xp = 0
    elit_xp = 0
    admin_xp = 0
    if has_daily:
        app_groups = daily_data.groupby('app').agg({
            'XP Earned': 'sum',
            'Active Minutes': 'sum',
            'Mastered Lessons': 'sum',
            'Correct Questions': 'sum',
            'Total Questions': 'sum',
            'Accuracy (%)': 'mean'
        }).reset_index()
        for _, ag in app_groups.iterrows():
            cat = categorize_app(ag['app'])
            xp_val = ag['XP Earned']
            if cat == 'Instruction':
                instr_xp += xp_val
            elif cat == 'Practice':
                practice_xp += xp_val
            elif cat == 'Testing':
                testing_xp += xp_val
            elif cat == 'Early Lit':
                elit_xp += xp_val
            else:
                admin_xp += xp_val
            app_breakdown.append({
                'app': ag['app'],
                'category': cat,
                'xp': round(xp_val, 1),
                'minutes': round(ag['Active Minutes'], 1),
                'mastered': int(ag['Mastered Lessons']),
                'correct': int(ag['Correct Questions']),
                'total_q': int(ag['Total Questions']),
                'accuracy': round(ag['Accuracy (%)'] * 100, 1) if ag['Accuracy (%)'] <= 1 else round(ag['Accuracy (%)'], 1)
            })
        app_breakdown.sort(key=lambda a: -a['xp'])

    pct_instr = round(instr_xp / total_xp * 100, 1) if total_xp > 0 else 0
    pct_practice = round(practice_xp / total_xp * 100, 1) if total_xp > 0 else 0
    pct_testing = round(testing_xp / total_xp * 100, 1) if total_xp > 0 else 0

    # Per-day activity (for timeline chart)
    daily_activity = []
    if has_daily:
        day_groups = daily_data.groupby(daily_data['date'].dt.date)['Active Minutes'].sum()
        for d in school_day_dates:
            mins = day_groups.get(d, 0)
            if START_DATE <= d <= END_DATE:
                daily_activity.append({'date': d.isoformat(), 'minutes': round(float(mins), 1)})

    # --- Test results aggregation ---
    has_tests = len(test_data) > 0
    test_history = []
    total_tests = 0
    eff_tests = 0
    doom_grades = []
    test_grades_tested = []

    if has_tests:
        total_tests = len(test_data)
        for _, tr in test_data.iterrows():
            passed = tr['score'] >= PASS_THRESHOLD if pd.notna(tr['score']) else False
            if passed:
                eff_tests += 1
            test_history.append({
                'date': tr['score_date_utc'].strftime('%Y-%m-%d') if pd.notna(tr['score_date_utc']) else '',
                'test_name': str(tr.get('test_name', '')),
                'grade': int(tr['test_grade']) if pd.notna(tr['test_grade']) else None,
                'score': round(tr['score'], 1) if pd.notna(tr['score']) else None,
                'type': str(tr.get('test_type', '')),
                'origin': str(tr.get('origin', '')),
                'passed': passed,
                'xp': round(tr['xp'], 1) if pd.notna(tr['xp']) else 0
            })
        test_history.sort(key=lambda t: t['date'])
        test_grades_tested = sorted(test_data['test_grade'].dropna().unique().tolist())

        # Doom loop detection: 3+ failed attempts at same grade, excluding grades eventually passed
        if has_tests:
            grade_fails = test_data[test_data['score'] < PASS_THRESHOLD].groupby('test_grade').size()
            grades_passed = set(int(g) for g in test_data[test_data['score'] >= PASS_THRESHOLD]['test_grade'].dropna().unique())
            doom_grades = [int(g) for g in grade_fails[grade_fails >= 3].index.tolist() if int(g) not in grades_passed]

    eff_rate = round(eff_tests / total_tests * 100, 1) if total_tests > 0 else 0

    # HMG fallback: if MAP HMG is missing or very low (0/1), try test results
    if (pd.isna(hmg) or hmg <= 1) and has_tests:
        passed_tests = test_data[test_data['score'] >= PASS_THRESHOLD]
        if len(passed_tests) > 0:
            test_hmg = passed_tests['test_grade'].max()
            # Only use test-derived HMG if it's better than current
            if pd.isna(hmg) or test_hmg > hmg:
                hmg = test_hmg

    # --- HMG+1 effective test rate (tests at the grade above final HMG) ---
    hmg_plus1_total = 0
    hmg_plus1_passed = 0
    hmg_plus1_days = set()
    if has_tests and test_history and pd.notna(hmg):
        target_grade = int(hmg) + 1
        for t in test_history:
            if t['grade'] == target_grade:
                hmg_plus1_total += 1
                if t['date']:
                    hmg_plus1_days.add(t['date'])
                if t['passed']:
                    hmg_plus1_passed += 1
    hmg_plus1_test_days = len(hmg_plus1_days)
    hmg_plus1_eff_rate = round(hmg_plus1_passed / hmg_plus1_total * 100, 1) if hmg_plus1_total > 0 else 0

    # --- Reading grade (HMG + 1) ---
    reading_grade = int(hmg + 1) if pd.notna(hmg) else None

    # --- Reading group assignment (G3-8 vs G9+) ---
    # G9+: HS level students with HMG >= 8 (reading grade >= 9)
    # G3-8: HMG 2-7 (any student) OR age grade 3-8 with HMG 2-12
    # Students with no usable HMG: assign by age grade if possible, else G3-8 default
    reading_group = ''
    if level == 'HS' and pd.notna(hmg) and hmg >= 8:
        reading_group = 'G9+'
    elif pd.notna(hmg) and 2 <= hmg <= 7:
        reading_group = 'G3-8'
    elif pd.notna(age_grade) and 3 <= age_grade <= 8 and pd.notna(hmg) and 2 <= hmg <= 12:
        reading_group = 'G3-8'
    elif pd.notna(hmg) and hmg >= 8 and level == 'HS':
        reading_group = 'G9+'
    elif pd.isna(hmg) or hmg <= 1:
        # No usable HMG — assign by age grade
        if pd.notna(age_grade) and age_grade >= 9 and level == 'HS':
            reading_group = 'G9+'
        else:
            reading_group = 'G3-8'
    else:
        # Catch-all: HMG 8-12 for non-HS students
        reading_group = 'G3-8'

    # --- HS reading category (uses post-fallback HMG) ---
    if level == 'HS':
        if pd.notna(hmg) and hmg <= 7:
            hs_reading_category = 'HS (≤G8)'
        elif pd.notna(hmg) and hmg >= 8:
            hs_reading_category = 'HS (G9+)'
        else:
            hs_reading_category = 'HS (No HMG)'
        level_display = hs_reading_category

    # --- Spring MAP / Year-over-year ---
    summer_slide = None
    if pd.notna(spring_rit) and pd.notna(fall_rit):
        summer_slide = float(fall_rit) - float(spring_rit)

    # --- Grade gap ---
    gap = None
    if pd.notna(hmg) and pd.notna(age_grade):
        gap = float(hmg) - float(age_grade)

    # --- Growth category ---
    if pd.notna(growth_fw):
        if growth_fw < 0:
            growth_cat = 'negative'
        elif growth_fw == 0:
            growth_cat = 'zero'
        else:
            growth_cat = 'positive'
    else:
        growth_cat = 'unknown'

    # --- 2x growth check (≥2 RIT points growth F→W) ---
    met_2x = False
    if pd.notna(growth_fw):
        met_2x = growth_fw >= 2

    # --- Issue detection ---
    issues = []
    # No instruction app (beyond G8) — needs HS reading instruction
    if pd.notna(hmg) and hmg >= 8:
        issues.append('NEEDS_HS_INSTRUCTION')
    # In MobyMax range but never enrolled in MobyMax
    elif pd.notna(hmg) and 2 <= hmg <= 7:
        ever_enrolled_mm = any(a['app'] == 'MobyMax' for a in app_breakdown)
        if not ever_enrolled_mm and has_daily:
            issues.append('NEEDS_MM_INSTRUCTION')
    # Over-testing
    if pct_testing > 50:
        issues.append('OVER_TESTING')
    # Doom loop (all grades)
    doom_loop_above_hmg = False
    if doom_grades:
        issues.append('DOOM_LOOP')
        # Check if any doom loop is above HMG (for systemic issue count)
        if pd.isna(hmg) or any(g > int(hmg) for g in doom_grades):
            doom_loop_above_hmg = True
    # Low minutes
    if pct_expected < 50:
        issues.append('LOW_ENGAGEMENT')
    # Time without growth
    if pct_expected >= 100 and pd.notna(growth_fw) and growth_fw <= 0:
        issues.append('TIME_NO_GROWTH')
    # At/ahead of grade with negative growth
    if pd.notna(gap) and gap >= 0 and pd.notna(growth_fw) and growth_fw < 0:
        issues.append('AT_GRADE_NO_MOTIVATION')
    # Large gap
    if pd.notna(gap) and gap <= -3:
        issues.append('LARGE_GAP')
    # Low effective test rate (at HMG+1)
    if hmg_plus1_total > 2 and hmg_plus1_eff_rate < 50:
        issues.append('LOW_EFFECTIVE_TESTS')

    return {
        'name': anon,
        'original_name': name,
        'email': email,
        'campus': campus,
        'level': level,
        'level_display': level_display,
        'hs_reading_category': hs_reading_category,
        'age_grade': int(age_grade) if pd.notna(age_grade) else None,
        'early_lit': early_lit == 'YES',
        'rit': float(rit) if pd.notna(rit) else None,
        'hmg': float(hmg) if pd.notna(hmg) else None,
        'reading_grade': reading_grade,
        'reading_group': reading_group,
        'fall_rit': float(fall_rit) if pd.notna(fall_rit) else None,
        'projected_rit': float(projected_rit) if pd.notna(projected_rit) else None,
        'winter_rit': float(winter_rit) if pd.notna(winter_rit) else None,
        'alpha_projected_growth': float(alpha_projected) if pd.notna(alpha_projected) else None,
        'growth': float(growth_fw) if pd.notna(growth_fw) else None,
        'growth_ww': float(growth_ww) if pd.notna(growth_ww) else None,
        'growth_category': growth_cat,
        'met_2x': met_2x,
        'eff_mastered': int(eff_mastered),
        'current_pred': str(current_pred) if pd.notna(current_pred) else '',
        'gap': round(gap, 1) if gap is not None else None,
        'deep_dive': deep_dive if deep_dive != 'nan' else '',
        'comments': comments,
        'rushed_map': rushed_map,
        'retake_recommended': retake_recommended,
        'was_pred_valid': was_pred_valid,
        'put_time': put_time,
        'earned_xp_flag': earned_xp_flag,
        'accuracy_flag': accuracy_flag,
        'mastered_1': mastered_1,
        # Daily metrics
        'has_daily_data': has_daily,
        'total_active_minutes': round(total_active, 1),
        'total_inactive_minutes': round(total_inactive, 1),
        'total_waste_minutes': round(total_waste, 1),
        'total_xp': round(total_xp, 1),
        'pct_expected': pct_expected,
        'daily_avg': daily_avg,
        'instr_xp': round(instr_xp, 1),
        'practice_xp': round(practice_xp, 1),
        'testing_xp': round(testing_xp, 1),
        'elit_xp': round(elit_xp, 1),
        'admin_xp': round(admin_xp, 1),
        'pct_instr': pct_instr,
        'pct_practice': pct_practice,
        'pct_testing': pct_testing,
        'app_breakdown': app_breakdown,
        'daily_activity': daily_activity,
        # Test results
        'has_test_data': has_tests,
        'total_tests': total_tests,
        'eff_tests': eff_tests,
        'eff_rate': eff_rate,
        'hmg_plus1_total': hmg_plus1_total,
        'hmg_plus1_passed': hmg_plus1_passed,
        'hmg_plus1_eff_rate': hmg_plus1_eff_rate,
        'hmg_plus1_test_days': hmg_plus1_test_days,
        'doom_grades': doom_grades,
        'doom_loop_above_hmg': doom_loop_above_hmg,
        'test_grades': [int(g) for g in test_grades_tested],
        'test_history': test_history,
        # Spring / YoY
        'spring_rit': float(spring_rit) if pd.notna(spring_rit) else None,
        'summer_slide': round(summer_slide, 1) if summer_slide is not None else None,
        # Issues
        'issues': issues,
    }


# ============================================================
# SYSTEMIC ISSUES DETECTION
# ============================================================
def detect_systemic_issues(students):
    """Analyze all students and return top 3 systemic issues."""
    issue_defs = {
        'NEEDS_HS_INSTRUCTION': {
            'title': 'Needs HS Reading Instruction',
            'desc': 'MobyMax caps at G8. Students at HMG 8+ need a high school reading instruction solution beyond Alpha Read.',
            'color': 'red',
        },
        'NEEDS_MM_INSTRUCTION': {
            'title': 'Needs MM Reading Instruction',
            'desc': 'Students within MobyMax range (HMG 2-7) have never been enrolled in MobyMax for structured reading instruction.',
            'color': 'orange',
        },
        'OVER_TESTING': {
            'title': 'Over-Testing & Test Doom Loops',
            'desc': 'Testing is assessment, not learning. Students trapped in test cycles accumulate XP but receive no instruction.',
            'color': 'red',
        },
        'TIME_NO_GROWTH': {
            'title': 'Minutes ≠ Growth — Quality of Engagement',
            'desc': 'Students met or exceeded expected reading minutes but still had zero or negative growth. Time alone is not the problem.',
            'color': 'orange',
        },
        'LOW_ENGAGEMENT': {
            'title': 'Low Engagement — Below 50% Expected Time',
            'desc': 'Students are far below the expected 25 min/day reading target, indicating attendance, scheduling, or motivation barriers.',
            'color': 'orange',
        },
        'DOOM_LOOP': {
            'title': 'Test Doom Loops',
            'desc': 'Students stuck retaking the same grade-level test 3+ times without passing (need 90%). Testing without instruction is unproductive.',
            'color': 'red',
        },
        'LARGE_GAP': {
            'title': 'Large Grade Gap — 3+ Grades Behind',
            'desc': 'Students are 3 or more grade levels behind age grade, indicating they may be overwhelmed by the gap.',
            'color': 'purple',
        },
        'LOW_EFFECTIVE_TESTS': {
            'title': 'Low Effective Test Rate',
            'desc': 'Students have taken 3+ tests at HMG+1 but fewer than half resulted in passing (≥90%). Only tests at the grade above the student\'s running HMG on the test date are counted.',
            'color': 'gray',
        },
        'AT_GRADE_NO_MOTIVATION': {
            'title': 'At/Ahead of Grade — Possible Motivation Issue',
            'desc': 'Students at or above grade level but with negative growth, suggesting engagement or motivation challenges.',
            'color': 'blue',
        },
    }

    # Count affected students per issue
    issue_counts = defaultdict(list)
    for s in students:
        for issue in s['issues']:
            issue_counts[issue].append(s)

    # Also combine OVER_TESTING and DOOM_LOOP
    combined_testing = set()
    for s in issue_counts.get('OVER_TESTING', []):
        combined_testing.add(s['email'])
    for s in issue_counts.get('DOOM_LOOP', []):
        combined_testing.add(s['email'])

    # Build ranked issues (merge OVER_TESTING + DOOM_LOOP into one)
    ranked = []
    seen_keys = set()

    # Special merged issue for over-testing + doom loops
    ot_students = issue_counts.get('OVER_TESTING', [])
    dl_students = issue_counts.get('DOOM_LOOP', [])
    dl_above_hmg_students = [s for s in dl_students if s.get('doom_loop_above_hmg', False)]
    merged_students = {s['email']: s for s in ot_students + dl_students}
    if len(merged_students) > 0:
        avg_g = np.nanmean([s['growth'] for s in merged_students.values() if s['growth'] is not None])
        ranked.append({
            'key': 'OVER_TESTING_DOOM',
            'title': 'Over-Testing & Test Doom Loops',
            'desc': 'Testing is assessment, not learning. Students spending &gt;50% XP on tests, or stuck retaking the same grade above HMG 3+ times without passing (need 90%).',
            'color': 'red',
            'count': len(merged_students),
            'avg_growth': round(avg_g, 1) if not np.isnan(avg_g) else None,
            'students': list(merged_students.values()),
            'detail_counts': {
                'over_testing': len(ot_students),
                'doom_loops': len(dl_above_hmg_students),
            }
        })
        seen_keys.add('OVER_TESTING')
        seen_keys.add('DOOM_LOOP')

    # Special merged issue for Missing Reading Instruction
    hs_instr = issue_counts.get('NEEDS_HS_INSTRUCTION', [])
    mm_instr = issue_counts.get('NEEDS_MM_INSTRUCTION', [])
    merged_instr = {s['email']: s for s in hs_instr + mm_instr}
    if len(merged_instr) > 0:
        avg_g = np.nanmean([s['growth'] for s in merged_instr.values() if s['growth'] is not None])
        ranked.append({
            'key': 'MISSING_READING_INSTRUCTION',
            'title': 'Missing Reading Instruction',
            'desc': 'Students without appropriate reading instruction. HMG 8+ students need HS-level reading instruction. HMG 2-7 students have never been enrolled in MobyMax.',
            'color': 'orange',
            'count': len(merged_instr),
            'avg_growth': round(avg_g, 1) if not np.isnan(avg_g) else None,
            'students': list(merged_instr.values()),
            'detail_counts': {
                'needs_hs': len(hs_instr),
                'needs_mm': len(mm_instr),
            }
        })
        seen_keys.add('NEEDS_HS_INSTRUCTION')
        seen_keys.add('NEEDS_MM_INSTRUCTION')

    # Special issue for Minutes ≠ Growth
    tng_students = issue_counts.get('TIME_NO_GROWTH', [])
    if len(tng_students) > 0:
        avg_g = np.nanmean([s['growth'] for s in tng_students if s['growth'] is not None])
        avg_daily_mins = round(np.mean([s['daily_avg'] for s in tng_students if s['daily_avg'] is not None]), 1)
        avg_pct = round(np.mean([s['pct_expected'] for s in tng_students]), 0)
        neg_growth = sum(1 for s in tng_students if s['growth'] is not None and s['growth'] < 0)
        ranked.append({
            'key': 'TIME_NO_GROWTH',
            'title': issue_defs['TIME_NO_GROWTH']['title'],
            'desc': issue_defs['TIME_NO_GROWTH']['desc'],
            'color': issue_defs['TIME_NO_GROWTH']['color'],
            'count': len(tng_students),
            'avg_growth': round(avg_g, 1) if not np.isnan(avg_g) else None,
            'students': tng_students,
            'detail_counts': {
                'avg_daily_minutes': avg_daily_mins,
                'avg_pct_expected': int(avg_pct),
                'neg_growth_count': neg_growth,
            }
        })
        seen_keys.add('TIME_NO_GROWTH')

    # Sort by count descending
    ranked.sort(key=lambda x: -x['count'])
    return ranked[:3]


# ============================================================
# HTML UTILITIES
# ============================================================
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
    if g is None:
        return ""
    if g < 0:
        return "growth-neg"
    if g == 0:
        return "growth-zero"
    return "growth-pos"


def growth_display(g):
    if g is None:
        return "&mdash;"
    if g > 0:
        return f"+{int(g)}"
    return str(int(g))


def pct_class(p):
    if p is None:
        return ""
    if p < 75:
        return "pct-warn"
    if p >= 100:
        return "pct-ok"
    return ""


def yes_no_html(val):
    val = str(val).strip()
    if val.lower() in ('yes', 'true'):
        return 'Yes'
    elif val.lower() in ('no', 'false', '', 'nan'):
        return '<span class="pct-warn">No</span>'
    return val


# ============================================================
# CSS
# ============================================================
SHARED_CSS = """
:root {
  --bg: #F8FAFC; --surface: #FFFFFF; --text: #0F172A; --muted: #475569; --border: #E2E8F0;
  --primary: #2563EB; --primary-hover: #1D4ED8; --accent: #06B6D4;
  --success: #16A34A; --warning: #F59E0B; --danger: #DC2626;
  --purple: #7C3AED;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; }
.container { max-width: 1200px; margin: 0 auto; padding: 20px; }

/* Header */
header { background: linear-gradient(135deg, var(--primary) 0%, var(--primary-hover) 100%); color: white; padding: 30px 0; margin-bottom: 0; }
header .container { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; }
header h1 { font-size: 1.6rem; font-weight: 700; }
header .subtitle { color: rgba(255,255,255,0.75); font-size: 0.95rem; }
.stats-bar { display: flex; gap: 12px; flex-wrap: wrap; }
.stat-pill { background: rgba(255,255,255,0.15); padding: 6px 14px; border-radius: 20px; font-size: 0.85rem; }
.stat-pill strong { color: var(--warning); }

/* Tabs */
.tab-bar { background: var(--primary-hover); border-bottom: 2px solid rgba(255,255,255,0.12); }
.tab-bar .container { display: flex; gap: 0; padding-top: 0; padding-bottom: 0; }
.tab-btn { background: none; border: none; color: rgba(255,255,255,0.6); padding: 12px 20px; font-size: 0.9rem; cursor: pointer; border-bottom: 3px solid transparent; transition: all 0.2s; font-family: inherit; }
.tab-btn:hover { color: white; background: rgba(255,255,255,0.05); }
.tab-btn.active { color: white; border-bottom-color: var(--accent); font-weight: 600; }
.tab-content { display: none; }
.tab-content.active { display: block; }

/* Sub-tabs (within Executive Summary) */
.sub-tabs { display: flex; gap: 0; margin-bottom: 20px; border-bottom: 2px solid var(--border); }
.sub-tab { background: none; border: none; color: var(--muted); padding: 10px 18px; font-size: 0.85rem; cursor: pointer; border-bottom: 3px solid transparent; transition: all 0.2s; font-family: inherit; }
.sub-tab:hover { color: var(--text); background: rgba(0,0,0,0.03); }
.sub-tab.active { color: var(--primary); border-bottom-color: var(--primary); font-weight: 600; }
.sub-pane { display: none; }
.sub-pane.active { display: block; }

/* KPI Cards */
.kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin: 24px 0; }
.kpi-card { background: var(--surface); border-radius: 10px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.04); text-align: center; border: 1px solid var(--border); }
.kpi-card .kpi-val { font-size: 2rem; font-weight: 800; }
.kpi-card .kpi-label { font-size: 0.8rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; }
.kpi-card.kpi-red .kpi-val { color: var(--danger); }
.kpi-card.kpi-green .kpi-val { color: var(--success); }
.kpi-card.kpi-blue .kpi-val { color: var(--primary); }

/* Issue Cards */
.issue-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 20px; margin: 20px 0; }
.issue-card { background: var(--surface); border-radius: 10px; padding: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.04); border-left: 5px solid var(--danger); border: 1px solid var(--border); border-left: 5px solid var(--danger); }
.issue-card.orange { border-left-color: var(--warning); }
.issue-card.purple { border-left-color: var(--purple); }
.issue-card.blue { border-left-color: var(--primary); }
.issue-card.gray { border-left-color: #94A3B8; }
.issue-card h3 { font-size: 1.05rem; margin-bottom: 8px; }
.issue-card .issue-num { display: inline-block; background: var(--danger); color: white; width: 26px; height: 26px; line-height: 26px; text-align: center; border-radius: 50%; font-weight: 700; font-size: 0.8rem; margin-right: 8px; }
.issue-card.orange .issue-num { background: var(--warning); }
.issue-card.purple .issue-num { background: var(--purple); }
.issue-card p { font-size: 0.88rem; color: var(--muted); margin-bottom: 8px; }
.mini-metrics { display: flex; gap: 12px; margin: 10px 0; flex-wrap: wrap; }
.mini-metric { background: var(--bg); padding: 6px 12px; border-radius: 6px; font-size: 0.82rem; }
.mini-metric .val { font-weight: 700; font-size: 1rem; }
.affected { font-size: 0.8rem; color: var(--muted); margin-top: 8px; }
.affected strong { color: var(--text); }

/* Filter bar */
.filter-bar { background: var(--surface); border-radius: 10px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); border: 1px solid var(--border); margin-bottom: 20px; display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
.filter-bar select, .filter-bar input { padding: 6px 10px; border: 1px solid var(--border); border-radius: 6px; font-size: 0.85rem; font-family: inherit; }
.filter-bar input { min-width: 160px; }
.filter-count { font-size: 0.85rem; color: var(--muted); margin-left: auto; }

/* Tables */
table { width: 100%; border-collapse: collapse; background: var(--surface); border-radius: 10px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.08); border: 1px solid var(--border); }
thead { background: var(--primary); color: white; }
th { padding: 10px 8px; text-align: left; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; white-space: nowrap; cursor: pointer; user-select: none; background: var(--primary); color: white; transition: background 0.15s; }
th:hover { background: var(--primary-hover); color: white; }
th .sort-arrow { font-size: 0.65rem; margin-left: 3px; opacity: 0.4; }
th.sorted .sort-arrow { opacity: 1; }
td { padding: 8px; font-size: 0.83rem; border-bottom: 1px solid var(--border); }
tbody tr:nth-child(even) { background: #F8FAFC; }
tbody tr:nth-child(odd) { background: var(--surface); }
tr:hover { background: #EFF6FF !important; }

/* Growth & status classes */
.growth-neg { color: var(--danger); font-weight: 700; }
.growth-zero { color: var(--warning); font-weight: 700; }
.growth-pos { color: var(--success); font-weight: 700; }
.pct-warn { color: var(--danger); font-weight: 600; }
.pct-ok { color: var(--success); }

/* Tags */
.tag { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 0.7rem; font-weight: 600; margin: 1px 2px; white-space: nowrap; }
.tag-red { background: #FEE2E2; color: #B91C1C; }
.tag-orange { background: #FEF3C7; color: #B45309; }
.tag-blue { background: #DBEAFE; color: #1D4ED8; }
.tag-purple { background: #EDE9FE; color: #6D28D9; }
.tag-gray { background: #F1F5F9; color: #475569; }
.tag-green { background: #DCFCE7; color: #15803D; }
.tag-yellow { background: #FEF9C3; color: #A16207; }

/* Student link */
a.student-link { color: var(--primary); text-decoration: none; font-weight: 600; }
a.student-link:hover { text-decoration: underline; color: var(--primary-hover); }

/* Campus cards */
.campus-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px; margin: 20px 0; }
.campus-card { background: var(--surface); border-radius: 10px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); border: 1px solid var(--border); }
.campus-card h3 { font-size: 1rem; margin-bottom: 8px; color: var(--text); }
.campus-card .campus-stats { display: flex; gap: 16px; flex-wrap: wrap; font-size: 0.85rem; }
.campus-card .campus-stat { text-align: center; }
.campus-card .campus-stat .val { font-size: 1.3rem; font-weight: 700; }
.campus-card .campus-stat .lbl { font-size: 0.72rem; color: var(--muted); text-transform: uppercase; }

/* Profile page styles */
.profile-header { background: linear-gradient(135deg, var(--primary) 0%, var(--primary-hover) 100%); color: white; padding: 24px 0; margin-bottom: 24px; }
.profile-header .container { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; max-width: 960px; }
.profile-header h1 { font-size: 1.5rem; }
.profile-header .badges { display: flex; gap: 8px; flex-wrap: wrap; }
.profile-header .grade-badge { background: rgba(255,255,255,0.18); padding: 4px 14px; border-radius: 16px; font-size: 0.85rem; }
.nav-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 8px; }
.nav-link { color: var(--primary); text-decoration: none; font-size: 0.9rem; }
.nav-link:hover { text-decoration: underline; color: var(--primary-hover); }
.back-link { font-weight: 600; }
.position-label { font-size: 0.8rem; color: var(--muted); }

/* Growth hero */
.growth-hero { display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }
.growth-box { background: var(--surface); border-radius: 10px; padding: 18px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); border: 1px solid var(--border); text-align: center; flex: 1; min-width: 130px; }
.growth-box .big-num { font-size: 2rem; font-weight: 800; }
.growth-box .label { font-size: 0.78rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; }

/* Metric cards */
.metric-card { background: var(--surface); border-radius: 10px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); border: 1px solid var(--border); margin-bottom: 20px; }
.metric-card h3 { font-size: 1rem; margin-bottom: 12px; color: var(--text); border-bottom: 2px solid var(--border); padding-bottom: 6px; }
.metric-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(100px, 1fr)); gap: 16px; }
.metric { text-align: center; }
.metric-val { font-size: 1.5rem; font-weight: 700; }
.metric-label { font-size: 0.75rem; color: var(--muted); text-transform: uppercase; }
.detail-line { font-size: 0.88rem; margin: 6px 0; }
.detail-line strong { color: var(--text); }
.muted { color: var(--muted); }

/* Stacked bar */
.stacked-bar { display: flex; height: 24px; border-radius: 6px; overflow: hidden; background: var(--border); margin: 10px 0; }
.bar-seg { height: 100%; }
.bar-seg.instr { background: var(--success); }
.bar-seg.practice { background: var(--primary); }
.bar-seg.test { background: var(--warning); }
.bar-seg.elit { background: var(--purple); }
.bar-seg.admin { background: #94A3B8; }
.bar-legend { display: flex; gap: 14px; flex-wrap: wrap; font-size: 0.78rem; margin-top: 6px; }
.legend-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 4px; vertical-align: middle; }

/* App table */
.app-table { width: 100%; border-collapse: collapse; margin-top: 10px; }
.app-table th { text-align: left; font-size: 0.75rem; text-transform: uppercase; color: white; padding: 8px 8px; background: var(--primary); cursor: default; }
.app-table td { padding: 8px; font-size: 0.85rem; border-bottom: 1px solid #F1F5F9; }

/* RIT timeline */
.rit-timeline { display: flex; align-items: center; gap: 12px; justify-content: center; flex-wrap: wrap; }
.rit-point { text-align: center; }
.rit-val { font-size: 1.4rem; font-weight: 700; }
.rit-label { font-size: 0.72rem; color: var(--muted); text-transform: uppercase; }
.rit-arrow { font-size: 1.2rem; color: var(--muted); }

/* Activity timeline */
.timeline-container { margin: 10px 0; }
.timeline-bars { display: flex; align-items: flex-end; height: 100px; gap: 1px; background: #F1F5F9; border-radius: 6px; padding: 4px 2px; }
.day-bar { flex: 1; border-radius: 2px 2px 0 0; min-width: 1px; position: relative; }
.day-bar.green { background: var(--success); }
.day-bar.blue { background: var(--primary); }
.day-bar.orange { background: var(--warning); }
.day-bar.zero { background: var(--border); height: 2px !important; }
.timeline-axis { display: flex; justify-content: space-between; font-size: 0.7rem; color: var(--muted); margin-top: 4px; padding: 0 2px; }
.timeline-legend { font-size: 0.75rem; color: var(--muted); margin-top: 6px; }
.timeline-legend span { margin-right: 12px; }

/* Alert */
.alert { padding: 10px 14px; border-radius: 8px; font-size: 0.85rem; margin-bottom: 14px; font-weight: 500; }
.alert-red { background: #FEE2E2; color: #B91C1C; border-left: 4px solid var(--danger); }
.alert-orange { background: #FEF3C7; color: #B45309; border-left: 4px solid var(--warning); }

/* Test history table */
.test-table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 0.82rem; }
.test-table th { text-align: left; font-size: 0.72rem; text-transform: uppercase; color: white; padding: 8px 6px; background: var(--primary); cursor: default; }
.test-table td { padding: 6px; border-bottom: 1px solid #F1F5F9; }
.app-table th:hover, .test-table th:hover { background: var(--primary-hover); }
.test-table .pass { color: var(--success); font-weight: 600; }
.test-table .fail { color: var(--danger); }

/* Comment */
.comment-text { font-style: italic; color: var(--muted); font-size: 0.9rem; background: var(--bg); padding: 12px; border-radius: 6px; }

/* Two-col layout */
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }

/* Section headings */
.section-heading { font-size: 1.3rem; margin: 30px 0 16px 0; color: var(--text); border-bottom: 3px solid var(--primary); display: inline-block; padding-bottom: 4px; }
.section-heading.red { border-bottom-color: var(--danger); }

/* Footer */
.footer { text-align: center; color: var(--muted); font-size: 0.8rem; padding: 30px 0; }

@media (max-width: 768px) {
  .issue-cards { grid-template-columns: 1fr; }
  .campus-grid { grid-template-columns: 1fr; }
  .two-col { grid-template-columns: 1fr; }
  table { font-size: 0.75rem; }
  th, td { padding: 6px 4px; }
  .tab-btn { padding: 10px 12px; font-size: 0.82rem; }
  .kpi-grid { grid-template-columns: repeat(2, 1fr); }
}
"""


# ============================================================
# DASHBOARD HTML GENERATION
# ============================================================
def generate_dashboard(students, campus_stats, systemic_issues, effective_days, expected_minutes):
    """Generate docs/crm/index.html."""
    total = len(students)
    students_with_growth = [s for s in students if s['growth'] is not None]
    avg_growth = np.mean([s['growth'] for s in students_with_growth]) if students_with_growth else 0
    neg_count = sum(1 for s in students_with_growth if s['growth'] < 0)
    pos_count = sum(1 for s in students_with_growth if s['growth'] > 0)
    met_2x = sum(1 for s in students if s['met_2x'])
    pct_met_2x = round(met_2x / total * 100) if total > 0 else 0

    # Reading group stats
    g38_students = [s for s in students if s['reading_group'] == 'G3-8']
    g9_students = [s for s in students if s['reading_group'] == 'G9+']

    g38_total = len(g38_students)
    g38_with_growth = [s for s in g38_students if s['growth'] is not None]
    g38_avg_growth = np.mean([s['growth'] for s in g38_with_growth]) if g38_with_growth else 0
    g38_neg = sum(1 for s in g38_with_growth if s['growth'] < 0)
    g38_pos = sum(1 for s in g38_with_growth if s['growth'] > 0)
    g38_met_2x = sum(1 for s in g38_students if s['met_2x'])
    g38_pct_2x = round(g38_met_2x / g38_total * 100) if g38_total > 0 else 0

    g9_total = len(g9_students)
    g9_with_growth = [s for s in g9_students if s['growth'] is not None]
    g9_avg_growth = np.mean([s['growth'] for s in g9_with_growth]) if g9_with_growth else 0
    g9_neg = sum(1 for s in g9_with_growth if s['growth'] < 0)
    g9_pos = sum(1 for s in g9_with_growth if s['growth'] > 0)
    g9_met_2x = sum(1 for s in g9_students if s['met_2x'])
    g9_pct_2x = round(g9_met_2x / g9_total * 100) if g9_total > 0 else 0

    # --- Issue cards ---
    issue_html = ""
    for i, issue in enumerate(systemic_issues, 1):
        color = issue['color']
        avg_g = f"{issue['avg_growth']:+.1f}" if issue['avg_growth'] is not None else "N/A"
        names = ", ".join([f'<a href="students/{s["slug"]}.html" class="student-link">{s["name"]}</a>' for s in issue['students'][:10]])
        if len(issue['students']) > 10:
            names += f" +more"

        detail_html = ""
        if 'detail_counts' in issue and issue['key'] == 'OVER_TESTING_DOOM':
            dc = issue['detail_counts']
            detail_html = f"""<div class="mini-metrics">
              <div class="mini-metric"><div class="val">{dc.get('over_testing', 0)}</div>over-testing (&gt;50% test XP)</div>
              <div class="mini-metric"><div class="val">{dc.get('doom_loops', 0)}</div>in test doom loops</div>
            </div>"""
        elif 'detail_counts' in issue and issue['key'] == 'MISSING_READING_INSTRUCTION':
            dc = issue['detail_counts']
            detail_html = f"""<div class="mini-metrics">
              <div class="mini-metric"><div class="val">{dc.get('needs_hs', 0)}</div>need HS reading instruction (HMG 8+)</div>
              <div class="mini-metric"><div class="val">{dc.get('needs_mm', 0)}</div>need MM reading instruction (HMG 2-7)</div>
            </div>"""
        elif 'detail_counts' in issue and issue['key'] == 'TIME_NO_GROWTH':
            dc = issue['detail_counts']
            detail_html = f"""<div class="mini-metrics">
              <div class="mini-metric"><div class="val">{dc.get('avg_daily_minutes', 0)}</div>avg minutes per day</div>
              <div class="mini-metric"><div class="val">{dc.get('avg_pct_expected', 0)}%</div>avg % of expected time</div>
              <div class="mini-metric"><div class="val">{dc.get('neg_growth_count', 0)}</div>with negative growth</div>
            </div>"""
        else:
            detail_html = f"""<div class="mini-metrics">
              <div class="mini-metric"><div class="val">{issue['count']}</div>students affected</div>
              <div class="mini-metric"><div class="val">{avg_g}</div>avg growth</div>
            </div>"""

        issue_html += f"""
        <div class="issue-card {color}">
          <h3><span class="issue-num">{i}</span>{issue['title']}</h3>
          <p>{issue['desc']}</p>
          {detail_html}
          <div class="affected"><strong>Students:</strong> {names}</div>
        </div>"""

    # --- Campus table rows ---
    sorted_campuses = sorted(campus_stats, key=lambda c: c['avg_growth'] if c['avg_growth'] is not None else 999)
    campus_rows = ""
    campus_js_data = []
    for idx, cs in enumerate(sorted_campuses):
        avg_g = growth_display(cs['avg_growth'])
        g_class = growth_class(cs['avg_growth'])
        pct2x = f"{cs['pct_met_2x']:.0f}%" if cs['pct_met_2x'] is not None else "&mdash;"
        campus_rows += f"""<tr data-idx="{idx}">
          <td>{cs['campus']}</td>
          <td>{cs['count']}</td>
          <td>{cs['levels']}</td>
          <td class="{g_class}">{avg_g}</td>
          <td>{cs['neg_count']}/{cs['count']}</td>
          <td>{pct2x}</td>
        </tr>"""
        campus_js_data.append({
            'n': cs['campus'], 'c': cs['count'],
            'ag': cs['avg_growth'], 'neg': cs['neg_count'],
            'pct2x': cs['pct_met_2x']
        })
    campus_js = json.dumps(campus_js_data, separators=(',', ':'))

    # --- Campus cards for Tab 2 ---
    campus_cards = ""
    for cs in sorted(campus_stats, key=lambda c: c['avg_growth'] if c['avg_growth'] is not None else 999):
        avg_g = growth_display(cs['avg_growth'])
        g_class = growth_class(cs['avg_growth'])
        # Top/bottom 3 students at this campus
        campus_students = [s for s in students if s['campus'] == cs['campus']]
        campus_students_with_growth = [s for s in campus_students if s['growth'] is not None]
        campus_students_with_growth.sort(key=lambda s: s['growth'])
        bottom3 = campus_students_with_growth[:3]
        top3 = campus_students_with_growth[-3:]
        top3.reverse()

        bottom_html = ""
        for s in bottom3:
            bottom_html += f'<a href="students/{s["slug"]}.html" class="student-link">{s["name"]}</a> ({growth_display(s["growth"])}), '
        bottom_html = bottom_html.rstrip(', ')

        top_html = ""
        for s in top3:
            top_html += f'<a href="students/{s["slug"]}.html" class="student-link">{s["name"]}</a> ({growth_display(s["growth"])}), '
        top_html = top_html.rstrip(', ')

        campus_cards += f"""
        <div class="campus-card">
          <h3>{cs['campus']}</h3>
          <div class="campus-stats">
            <div class="campus-stat"><div class="val">{cs['count']}</div><div class="lbl">Students</div></div>
            <div class="campus-stat"><div class="val {g_class}">{avg_g}</div><div class="lbl">Avg Growth</div></div>
            <div class="campus-stat"><div class="val">{cs['neg_count']}</div><div class="lbl">Neg Growth</div></div>
            <div class="campus-stat"><div class="val">{cs['levels']}</div><div class="lbl">Levels</div></div>
          </div>
          <p class="detail-line" style="margin-top:10px;"><strong>Lowest:</strong> {bottom_html}</p>
          <p class="detail-line"><strong>Highest:</strong> {top_html}</p>
        </div>"""

    # --- Inline student data for JS filtering ---
    js_data = []
    for idx, s in enumerate(students):
        js_data.append({
            'i': idx,
            'n': s['name'],
            'c': s['campus'],
            'l': s['level'],
            'ld': s['level_display'],
            'rg': s['reading_group'],
            'g': s['age_grade'],
            'el': s['early_lit'],
            'gr': s['growth'],
            'gc': s['growth_category'],
            'dd': s['deep_dive'],
            'hmg': s['hmg'],
            'm2x': s['met_2x'],
        })
    js_json = json.dumps(js_data, separators=(',', ':'))

    # --- Student table rows ---
    table_rows = ""
    for idx, s in enumerate(students):
        dd_class = ''
        g_class = growth_class(s['growth'])
        pct_cl = pct_class(s['pct_expected'])
        eff_str = f"{s['eff_rate']:.0f}%" if s['total_tests'] > 0 else "&mdash;"
        eff_cl = "pct-warn" if s['total_tests'] > 0 and s['eff_rate'] < 50 else ""
        fall_str = fmt_num(s['fall_rit'])
        winter_str = fmt_num(s['winter_rit'])

        # Issue tags
        tags = ""
        if 'NEEDS_HS_INSTRUCTION' in s['issues']:
            tags += '<span class="tag tag-red">Needs HS Reading</span> '
        if 'OVER_TESTING' in s['issues']:
            tags += '<span class="tag tag-red">Over-Testing</span> '
        if 'DOOM_LOOP' in s['issues']:
            tags += '<span class="tag tag-red">Doom Loop</span> '
        if 'LOW_ENGAGEMENT' in s['issues']:
            tags += '<span class="tag tag-orange">Low Engagement</span> '
        if 'TIME_NO_GROWTH' in s['issues']:
            tags += '<span class="tag tag-yellow">Time≠Growth</span> '
        if 'NEEDS_MM_INSTRUCTION' in s['issues']:
            tags += '<span class="tag tag-orange">Needs MM Reading</span> '
        if 'AT_GRADE_NO_MOTIVATION' in s['issues']:
            tags += '<span class="tag tag-blue">At Grade</span> '
        if 'LARGE_GAP' in s['issues']:
            tags += '<span class="tag tag-purple">Large Gap</span> '
        # HS reading category tag
        if s['hs_reading_category'] == 'HS (G9+)':
            tags += '<span class="tag tag-purple">G9+ Reading</span> '
        if not tags.strip():
            if s['growth'] is not None and s['growth'] > 0:
                tags = '<span class="tag tag-green">Growing</span>'
            else:
                tags = ''

        table_rows += f"""<tr{dd_class} data-idx="{idx}">
          <td><a class="student-link" href="students/{s['slug']}.html">{s['name']}</a></td>
          <td>{s['campus'].replace('Alpha School ', '').replace('Alpha ', '')}</td>
          <td>{s['level_display']}</td>
          <td>{s['age_grade'] if s['age_grade'] is not None else '&mdash;'}</td>
          <td>{fmt_num(s['hmg'])}</td>
          <td class="{g_class}">{growth_display(s['growth'])}</td>
          <td>{fall_str}</td>
          <td>{winter_str}</td>
          <td class="{pct_cl}">{fmt_num(s['pct_expected'])}%</td>
          <td>{fmt_num(s['total_xp'])}</td>
          <td class="{eff_cl}">{eff_str}</td>
          <td>{tags}</td>
        </tr>"""

    # Build filter dropdowns
    campuses = sorted(set(s['campus'] for s in students))
    level_displays = sorted(set(s['level_display'] for s in students if s['level_display']))
    grades = sorted(set(s['age_grade'] for s in students if s['age_grade'] is not None))

    campus_opts = '<option value="">All Campuses</option>'
    for c in campuses:
        campus_opts += f'<option value="{c}">{c.replace("Alpha School ", "").replace("Alpha ", "")}</option>'
    level_opts = '<option value="">All Levels</option>'
    for ld in level_displays:
        level_opts += f'<option value="{ld}">{ld}</option>'
    grade_opts = '<option value="">All Grades</option>'
    for g in grades:
        grade_opts += f'<option value="{g}">Grade {g}</option>'
    hmg_values = sorted(set(int(s['hmg']) for s in students if s['hmg'] is not None))
    hmg_opts = '<option value="">All HMG</option>'
    for h in hmg_values:
        hmg_opts += f'<option value="{h}">HMG {h}</option>'
    hmg_opts += '<option value="none">No HMG</option>'

    # Build the HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Reading 3+ Results - Winter 2025-26 MAP Analysis</title>
<style>{SHARED_CSS}</style>
</head>
<body>

<header>
  <div class="container">
    <div>
      <h1>Reading 3+ Results</h1>
      <div class="subtitle">Winter 2025-26 MAP Analysis &middot; All Campuses &middot; <span style="background:rgba(255,255,255,0.2); padding:2px 10px; border-radius:10px; font-size:0.8rem;">Updated Feb 9</span></div>
    </div>
    <div class="stats-bar">
      <div class="stat-pill"><strong>{total}</strong> students</div>
      <div class="stat-pill">Avg growth: <strong>{avg_growth:+.1f} RIT</strong></div>
      <div class="stat-pill"><strong>{effective_days}</strong> school days</div>
      <div class="stat-pill">Aug 14 &ndash; Jan 23</div>
    </div>
  </div>
</header>

<div class="tab-bar">
  <div class="container">
    <button class="tab-btn active" onclick="showTab('summary')">Executive Summary</button>
    <button class="tab-btn" onclick="showTab('campus')">Campus Breakdown</button>
    <button class="tab-btn" onclick="showTab('students')">All Students</button>
  </div>
</div>

<div class="container">

<!-- TAB 1: EXECUTIVE SUMMARY -->
<div id="tab-summary" class="tab-content active">

  <div class="sub-tabs">
    <button class="sub-tab active" onclick="showSubTab('all')">All Students</button>
    <button class="sub-tab" onclick="showSubTab('g38')">Reading G3&ndash;8</button>
    <button class="sub-tab" onclick="showSubTab('g9')">Reading G9+</button>
  </div>

  <div id="sub-all" class="sub-pane active">
    <div class="kpi-grid">
      <div class="kpi-card"><div class="kpi-val">{total}</div><div class="kpi-label">Total Reading Students</div></div>
      <div class="kpi-card {'kpi-red' if avg_growth < 0 else 'kpi-green' if avg_growth > 0 else ''}"><div class="kpi-val">{avg_growth:+.1f}</div><div class="kpi-label">Avg RIT Growth (F&rarr;W)</div></div>
      <div class="kpi-card"><div class="kpi-val">{pct_met_2x}%</div><div class="kpi-label">Met 2x Growth Target</div></div>
      <div class="kpi-card kpi-red"><div class="kpi-val">{neg_count}</div><div class="kpi-label">Negative Growth</div></div>
    </div>
  </div>

  <div id="sub-g38" class="sub-pane">
    <div class="kpi-grid">
      <div class="kpi-card"><div class="kpi-val">{g38_total}</div><div class="kpi-label">Students</div></div>
      <div class="kpi-card {'kpi-red' if g38_avg_growth < 0 else 'kpi-green' if g38_avg_growth > 0 else ''}"><div class="kpi-val">{g38_avg_growth:+.1f}</div><div class="kpi-label">Avg Growth</div></div>
      <div class="kpi-card"><div class="kpi-val">{g38_pct_2x}%</div><div class="kpi-label">Met 2x Target</div></div>
      <div class="kpi-card kpi-red"><div class="kpi-val">{g38_neg}</div><div class="kpi-label">Negative Growth</div></div>
    </div>
  </div>

  <div id="sub-g9" class="sub-pane">
    <div class="kpi-grid">
      <div class="kpi-card"><div class="kpi-val">{g9_total}</div><div class="kpi-label">Students</div></div>
      <div class="kpi-card {'kpi-red' if g9_avg_growth < 0 else 'kpi-green' if g9_avg_growth > 0 else ''}"><div class="kpi-val">{g9_avg_growth:+.1f}</div><div class="kpi-label">Avg Growth</div></div>
      <div class="kpi-card"><div class="kpi-val">{g9_pct_2x}%</div><div class="kpi-label">Met 2x Target</div></div>
      <div class="kpi-card kpi-red"><div class="kpi-val">{g9_neg}</div><div class="kpi-label">Negative Growth</div></div>
    </div>
  </div>

  <h2 class="section-heading red" style="margin-top:30px;">Top 3 Systemic Issues</h2>
  <div class="issue-cards">
    {issue_html}
  </div>

  <h2 class="section-heading">Campus Performance</h2>
  <div style="overflow-x:auto;">
  <table id="campus-table">
    <thead><tr>
      <th onclick="sortCampus(0,'n',false)">Campus <span class="sort-arrow">&#9650;</span></th>
      <th onclick="sortCampus(1,'c',true)">Students <span class="sort-arrow">&#9650;</span></th>
      <th>Levels</th>
      <th onclick="sortCampus(3,'ag',true)">Avg Growth <span class="sort-arrow">&#9650;</span></th>
      <th onclick="sortCampus(4,'neg',true)">Neg Growth <span class="sort-arrow">&#9650;</span></th>
      <th onclick="sortCampus(5,'pct2x',true)">Met 2x <span class="sort-arrow">&#9650;</span></th>
    </tr></thead>
    <tbody>{campus_rows}</tbody>
  </table>
  </div>

  <h2 class="section-heading" style="margin-top:30px;">Growth Distribution</h2>
  <div class="kpi-grid">
    <div class="kpi-card kpi-red"><div class="kpi-val">{neg_count}</div><div class="kpi-label">Negative Growth</div></div>
    <div class="kpi-card"><div class="kpi-val">{sum(1 for s in students_with_growth if s['growth'] == 0)}</div><div class="kpi-label">Zero Growth</div></div>
    <div class="kpi-card kpi-green"><div class="kpi-val">{pos_count}</div><div class="kpi-label">Positive Growth</div></div>
    <div class="kpi-card"><div class="kpi-val">{total - len(students_with_growth)}</div><div class="kpi-label">No Growth Data</div></div>
  </div>
</div>

<!-- TAB 2: CAMPUS BREAKDOWN -->
<div id="tab-campus" class="tab-content">
  <h2 class="section-heading">Campus Breakdown</h2>
  <div class="campus-grid">
    {campus_cards}
  </div>
</div>

<!-- TAB 3: ALL STUDENTS -->
<div id="tab-students" class="tab-content">

  <div class="filter-bar">
    <select id="f-campus" onchange="applyFilters()">{campus_opts}</select>
    <select id="f-level" onchange="applyFilters()">{level_opts}</select>
    <select id="f-grade" onchange="applyFilters()">{grade_opts}</select>
    <select id="f-hmg" onchange="applyFilters()">{hmg_opts}</select>
    <select id="f-growth" onchange="applyFilters()">
      <option value="">All Growth</option>
      <option value="negative">Negative</option>
      <option value="zero">Zero</option>
      <option value="positive">Positive</option>
    </select>
    <select id="f-earlylit" onchange="applyFilters()">
      <option value="">All</option>
      <option value="yes">Early Lit</option>
      <option value="no">Not Early Lit</option>
    </select>
    <input type="text" id="f-search" placeholder="Search name..." oninput="applyFilters()">
    <span class="filter-count" id="filter-count">{total} students</span>
  </div>

  <div id="filter-summary" class="kpi-grid" style="margin-bottom:20px;">
    <div class="kpi-card"><div class="kpi-val" id="fs-count">{total}</div><div class="kpi-label">Students</div></div>
    <div class="kpi-card"><div class="kpi-val" id="fs-growth">{avg_growth:+.1f}</div><div class="kpi-label">Avg Growth</div></div>
    <div class="kpi-card"><div class="kpi-val" id="fs-2x">{pct_met_2x}%</div><div class="kpi-label">Met 2x Target</div></div>
    <div class="kpi-card"><div class="kpi-val" id="fs-neg">{neg_count}</div><div class="kpi-label">Negative Growth</div></div>
  </div>

  <div style="overflow-x:auto;">
  <table id="student-table">
    <thead><tr>
      <th onclick="sortTable(0,'n',false)">Student <span class="sort-arrow">&#9650;</span></th>
      <th onclick="sortTable(1,'c',false)">Campus <span class="sort-arrow">&#9650;</span></th>
      <th onclick="sortTable(2,'ld',false)">Level <span class="sort-arrow">&#9650;</span></th>
      <th onclick="sortTable(3,'g',true)">Gr <span class="sort-arrow">&#9650;</span></th>
      <th>HMG</th>
      <th onclick="sortTable(5,'gr',true)">Growth <span class="sort-arrow">&#9650;</span></th>
      <th>Fall RIT</th>
      <th>Win RIT</th>
      <th>% Exp Time</th>
      <th>Total XP</th>
      <th>Eff%</th>
      <th>Issues</th>
    </tr></thead>
    <tbody>
      {table_rows}
    </tbody>
  </table>
  </div>
</div>

</div>

<div class="footer">
  Reading 3+ Results &middot; Winter 2025-26 MAP Analysis &middot; Updated Feb 9, 2026
</div>

<script>
const S={js_json};

function showTab(id) {{
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-'+id).classList.add('active');
  event.target.classList.add('active');
}}

function showSubTab(id) {{
  document.querySelectorAll('.sub-pane').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.sub-tab').forEach(b => b.classList.remove('active'));
  document.getElementById('sub-'+id).classList.add('active');
  event.target.classList.add('active');
}}

function applyFilters() {{
  const campus = document.getElementById('f-campus').value;
  const level = document.getElementById('f-level').value;
  const grade = document.getElementById('f-grade').value;
  const hmgF = document.getElementById('f-hmg').value;
  const growth = document.getElementById('f-growth').value;
  const el = document.getElementById('f-earlylit').value;
  const search = document.getElementById('f-search').value.toLowerCase();
  const rows = document.querySelectorAll('#student-table tbody tr');
  let vis = 0;
  let sumGrowth = 0, countGrowth = 0, countNeg = 0, count2x = 0;
  rows.forEach(row => {{
    const i = parseInt(row.dataset.idx);
    const s = S[i];
    let show = true;
    if (campus && s.c !== campus) show = false;
    if (level && s.ld !== level) show = false;
    if (grade && s.g != grade) show = false;
    if (hmgF === 'none' && s.hmg != null) show = false;
    if (hmgF && hmgF !== 'none' && (s.hmg == null || Math.floor(s.hmg) != parseInt(hmgF))) show = false;
    if (growth && s.gc !== growth) show = false;
    if (el === 'yes' && !s.el) show = false;
    if (el === 'no' && s.el) show = false;
    if (search && !s.n.toLowerCase().includes(search)) show = false;
    row.style.display = show ? '' : 'none';
    if (show) {{
      vis++;
      if (s.gr != null) {{ sumGrowth += s.gr; countGrowth++; if (s.gr < 0) countNeg++; }}
      if (s.m2x) count2x++;
    }}
  }});
  document.getElementById('filter-count').textContent = vis + ' students';
  const avgG = countGrowth > 0 ? (sumGrowth / countGrowth) : 0;
  const pct2x = vis > 0 ? Math.round(count2x / vis * 100) : 0;
  document.getElementById('fs-count').textContent = vis;
  document.getElementById('fs-growth').textContent = (avgG >= 0 ? '+' : '') + avgG.toFixed(1);
  document.getElementById('fs-2x').textContent = pct2x + '%';
  document.getElementById('fs-neg').textContent = countNeg;
  // Color the avg growth
  const gEl = document.getElementById('fs-growth');
  gEl.className = 'kpi-val' + (avgG < 0 ? ' growth-neg' : avgG > 0 ? ' growth-pos' : '');
}}

let curSort = {{col: null, asc: true}};
function sortTable(ci, key, num) {{
  const tb = document.querySelector('#student-table tbody');
  const rows = Array.from(tb.querySelectorAll('tr'));
  if (curSort.col === ci) curSort.asc = !curSort.asc;
  else curSort = {{col: ci, asc: true}};
  rows.sort((a, b) => {{
    const ai = parseInt(a.dataset.idx), bi = parseInt(b.dataset.idx);
    let av = S[ai][key], bv = S[bi][key];
    if (av == null) return 1;
    if (bv == null) return -1;
    const cmp = num ? (av - bv) : String(av).localeCompare(String(bv));
    return curSort.asc ? cmp : -cmp;
  }});
  rows.forEach(r => tb.appendChild(r));
}}

const CS={campus_js};
let campSort={{col:null,asc:true}};
function sortCampus(ci,key,num){{
  const tb=document.querySelector('#campus-table tbody');
  const rows=Array.from(tb.querySelectorAll('tr'));
  if(campSort.col===ci) campSort.asc=!campSort.asc;
  else campSort={{col:ci,asc:true}};
  rows.sort((a,b)=>{{
    const ai=parseInt(a.dataset.idx),bi=parseInt(b.dataset.idx);
    let av=CS[ai][key],bv=CS[bi][key];
    if(av==null) return 1; if(bv==null) return -1;
    const cmp=num?(av-bv):String(av).localeCompare(String(bv));
    return campSort.asc?cmp:-cmp;
  }});
  rows.forEach(r=>tb.appendChild(r));
}}
</script>

</body>
</html>"""

    filepath = os.path.join(OUT_DIR, "index.html")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Dashboard: {filepath}")


# ============================================================
# STUDENT DETAIL PAGE GENERATION
# ============================================================
def generate_student_page(student, prev_student, next_student, position, total, expected_minutes):
    """Generate one student detail page."""
    s = student

    # Nav links
    prev_link = ""
    next_link = ""
    if prev_student:
        prev_link = f'<a href="{prev_student["slug"]}.html" class="nav-link">&larr; {prev_student["name"]}</a>'
    if next_student:
        next_link = f'<a href="{next_student["slug"]}.html" class="nav-link">{next_student["name"]} &rarr;</a>'

    # Issue tags
    issue_tags = ""
    issue_tag_map = {
        'NEEDS_HS_INSTRUCTION': ('Needs HS Reading Instruction', 'tag-red'),
        'NEEDS_MM_INSTRUCTION': ('Needs MM Reading Instruction', 'tag-orange'),
        'OVER_TESTING': ('Over-Testing', 'tag-red'),
        'DOOM_LOOP': ('Doom Loop', 'tag-red'),
        'LOW_ENGAGEMENT': ('Low Engagement', 'tag-orange'),
        'TIME_NO_GROWTH': ('Time ≠ Growth', 'tag-yellow'),
        'AT_GRADE_NO_MOTIVATION': ('At/Ahead of Grade', 'tag-blue'),
        'LARGE_GAP': ('Large Gap', 'tag-purple'),
        'LOW_EFFECTIVE_TESTS': ('Low Effective Tests', 'tag-gray'),
    }
    for issue in s['issues']:
        label, cls = issue_tag_map.get(issue, (issue, 'tag-gray'))
        issue_tags += f'<span class="tag {cls}">{label}</span> '
    # HS reading category tag on detail page
    if s['hs_reading_category']:
        cat_cls = 'tag-purple' if 'G9+' in s['hs_reading_category'] else 'tag-blue'
        issue_tags += f' <span class="tag {cat_cls}">{s["hs_reading_category"]}</span>'
    if not issue_tags.strip():
        if s['growth'] is not None and s['growth'] > 0:
            issue_tags = '<span class="tag tag-green">Positive Growth</span>'
        else:
            issue_tags = '<span class="tag tag-gray">No critical flags</span>'

    # --- Daily Activity Timeline ---
    timeline_html = ""
    if s['daily_activity']:
        max_mins = max((d['minutes'] for d in s['daily_activity']), default=1)
        if max_mins == 0:
            max_mins = 1
        bars = ""
        for d in s['daily_activity']:
            m = d['minutes']
            pct = min(m / max_mins * 100, 100)
            if m == 0:
                bars += f'<div class="day-bar zero" title="{d["date"]}: 0 min"></div>'
            elif m >= 25:
                bars += f'<div class="day-bar green" style="height:{pct:.0f}%" title="{d["date"]}: {m:.0f} min"></div>'
            elif m >= 10:
                bars += f'<div class="day-bar blue" style="height:{pct:.0f}%" title="{d["date"]}: {m:.0f} min"></div>'
            else:
                bars += f'<div class="day-bar orange" style="height:{pct:.0f}%" title="{d["date"]}: {m:.0f} min"></div>'

        timeline_html = f"""
        <div class="metric-card">
          <h3>Daily Activity Timeline (Aug &ndash; Jan)</h3>
          <div class="timeline-container">
            <div class="timeline-bars">{bars}</div>
            <div class="timeline-axis">
              <span>Aug</span><span>Sep</span><span>Oct</span><span>Nov</span><span>Dec</span><span>Jan</span>
            </div>
            <div class="timeline-legend">
              <span><span class="legend-dot" style="background:var(--success);"></span> &ge;25 min</span>
              <span><span class="legend-dot" style="background:var(--primary);"></span> 10-24 min</span>
              <span><span class="legend-dot" style="background:var(--warning);"></span> &lt;10 min</span>
              <span><span class="legend-dot" style="background:var(--border);"></span> 0 min</span>
            </div>
          </div>
        </div>"""
    elif not s['has_daily_data']:
        timeline_html = """
        <div class="metric-card">
          <h3>Daily Activity Timeline</h3>
          <p class="muted">No daily activity data available for this student.</p>
        </div>"""

    # --- App Breakdown ---
    app_bar_html = ""
    app_table_rows = ""
    if s['total_xp'] > 0:
        pct_i = s['instr_xp'] / s['total_xp'] * 100
        pct_p = s['practice_xp'] / s['total_xp'] * 100
        pct_t = s['testing_xp'] / s['total_xp'] * 100
        pct_e = s['elit_xp'] / s['total_xp'] * 100
        pct_a = s['admin_xp'] / s['total_xp'] * 100
        app_bar_html = f"""<div class="stacked-bar">
          <div class="bar-seg instr" style="width:{pct_i:.1f}%" title="Instruction: {fmt_num(s['instr_xp'])} XP ({pct_i:.0f}%)"></div>
          <div class="bar-seg practice" style="width:{pct_p:.1f}%" title="Practice: {fmt_num(s['practice_xp'])} XP ({pct_p:.0f}%)"></div>
          <div class="bar-seg test" style="width:{pct_t:.1f}%" title="Testing: {fmt_num(s['testing_xp'])} XP ({pct_t:.0f}%)"></div>
          <div class="bar-seg elit" style="width:{pct_e:.1f}%" title="Early Lit: {fmt_num(s['elit_xp'])} XP ({pct_e:.0f}%)"></div>
          <div class="bar-seg admin" style="width:{pct_a:.1f}%" title="Admin/Other: {fmt_num(s['admin_xp'])} XP ({pct_a:.0f}%)"></div>
        </div>"""

    for app in s['app_breakdown']:
        cat_cls = {'Instruction': 'tag-green', 'Practice': 'tag-blue', 'Testing': 'tag-orange', 'Early Lit': 'tag-purple'}.get(app['category'], 'tag-gray')
        pct_of_total = round(app['xp'] / s['total_xp'] * 100, 1) if s['total_xp'] > 0 else 0
        app_table_rows += f"""<tr>
          <td>{app['app']}</td>
          <td><span class="tag {cat_cls}">{app['category']}</span></td>
          <td>{fmt_num(app['xp'])}</td>
          <td>{fmt_num(app['minutes'])}</td>
          <td>{app['mastered']}</td>
          <td>{app['accuracy']:.0f}%</td>
          <td>{pct_of_total:.1f}%</td>
        </tr>"""

    xp_section = ""
    if s['total_xp'] > 0 or s['app_breakdown']:
        practice_legend = f'<span><span class="legend-dot" style="background:var(--primary);"></span> Practice ({fmt_num(s["practice_xp"])} XP, {fmt_num(s["pct_practice"])}%)</span>' if s['practice_xp'] > 0 else ''
        elit_legend = f'<span><span class="legend-dot" style="background:var(--purple);"></span> Early Lit ({fmt_num(s["elit_xp"])} XP)</span>' if s['elit_xp'] > 0 else ''
        admin_legend = f'<span><span class="legend-dot" style="background:#94A3B8;"></span> Other ({fmt_num(s["admin_xp"])} XP)</span>' if s['admin_xp'] > 0 else ''
        xp_section = f"""
        <div class="metric-card">
          <h3>XP Breakdown by Category</h3>
          {app_bar_html}
          <div class="bar-legend">
            <span><span class="legend-dot" style="background:var(--success);"></span> Instruction ({fmt_num(s['instr_xp'])} XP, {fmt_num(s['pct_instr'])}%)</span>
            {practice_legend}
            <span><span class="legend-dot" style="background:var(--warning);"></span> Testing ({fmt_num(s['testing_xp'])} XP, {fmt_num(s['pct_testing'])}%)</span>
            {elit_legend}
            {admin_legend}
          </div>
          <table class="app-table">
            <thead><tr><th>App</th><th>Category</th><th>XP</th><th>Minutes</th><th>Mastered</th><th>Accuracy</th><th>% of Total</th></tr></thead>
            <tbody>{app_table_rows}</tbody>
          </table>
        </div>"""
    elif not s['has_daily_data']:
        xp_section = """
        <div class="metric-card">
          <h3>XP Breakdown</h3>
          <p class="muted">No daily XP data available for this student.</p>
        </div>"""
    else:
        xp_section = """
        <div class="metric-card">
          <h3>XP Breakdown</h3>
          <p class="muted">No XP earned during this period.</p>
        </div>"""

    # --- Waste Detection ---
    waste_html = ""
    if s['has_daily_data'] and (s['total_inactive_minutes'] > 0 or s['total_waste_minutes'] > 0):
        total_time = s['total_active_minutes'] + s['total_inactive_minutes'] + s['total_waste_minutes']
        waste_pct = round((s['total_inactive_minutes'] + s['total_waste_minutes']) / total_time * 100, 1) if total_time > 0 else 0
        waste_cls = "pct-warn" if waste_pct > 20 else ""
        waste_html = f"""
        <div class="metric-card">
          <h3>Waste Detection</h3>
          <div class="metric-grid">
            <div class="metric"><div class="metric-val">{fmt_num(s['total_inactive_minutes'])}</div><div class="metric-label">Inactive Min</div></div>
            <div class="metric"><div class="metric-val">{fmt_num(s['total_waste_minutes'])}</div><div class="metric-label">Waste Min</div></div>
            <div class="metric"><div class="metric-val {waste_cls}">{waste_pct}%</div><div class="metric-label">% Non-Active</div></div>
          </div>
        </div>"""

    # --- Test History ---
    test_html = ""
    if s['total_tests'] > 0:
        doom_str = ""
        if s['doom_grades']:
            doom_str = f'<div class="alert alert-red">Doom loop detected on grade(s): {", ".join(["G" + str(g) for g in s["doom_grades"]])}</div>'

        test_rows = ""
        for t in s['test_history']:
            score_str = f"{t['score']:.0f}%" if t['score'] is not None else "&mdash;"
            pass_cls = "pass" if t['passed'] else "fail"
            pass_str = "Pass" if t['passed'] else "Fail"
            test_rows += f"""<tr>
              <td>{t['date']}</td>
              <td>{t['test_name'][:40]}</td>
              <td>G{t['grade'] if t['grade'] is not None else '?'}</td>
              <td class="{pass_cls}">{score_str}</td>
              <td class="{pass_cls}">{pass_str}</td>
              <td>{t['type']}</td>
              <td>{t['origin']}</td>
            </tr>"""

        eff_cl = pct_class(s['eff_rate'])
        test_html = f"""
        <div class="metric-card">
          <h3>Test History</h3>
          {doom_str}
          <div class="metric-grid">
            <div class="metric"><div class="metric-val">{s['total_tests']}</div><div class="metric-label">Total Tests</div></div>
            <div class="metric"><div class="metric-val">{s['eff_tests']}</div><div class="metric-label">Passed (&ge;90%)</div></div>
            <div class="metric"><div class="metric-val {eff_cl}">{s['eff_rate']:.0f}%</div><div class="metric-label">Pass Rate</div></div>
          </div>
          <p class="detail-line" style="margin-top:8px;"><strong>Grades tested:</strong> {", ".join(["G" + str(g) for g in s['test_grades']])}</p>
          <div style="overflow-x:auto; margin-top:12px;">
          <table class="test-table">
            <thead><tr><th>Date</th><th>Test</th><th>Grade</th><th>Score</th><th>Result</th><th>Type</th><th>Origin</th></tr></thead>
            <tbody>{test_rows}</tbody>
          </table>
          </div>
        </div>"""
    else:
        test_html = """
        <div class="metric-card">
          <h3>Test History</h3>
          <p class="muted">No reading tests taken during this period.</p>
        </div>"""

    # --- Year-over-Year ---
    yoy_html = ""
    if s['spring_rit'] is not None:
        slide_str = ""
        if s['summer_slide'] is not None:
            if s['summer_slide'] > 0:
                slide_str = f'<span class="growth-neg">Lost {int(s["summer_slide"])} RIT over summer</span>'
            elif s['summer_slide'] < 0:
                slide_str = f'<span class="growth-pos">Gained {int(abs(s["summer_slide"]))} RIT over summer</span>'
            else:
                slide_str = '<span>No summer change</span>'
        yoy_html = f"""
        <div class="metric-card">
          <h3>Year-over-Year</h3>
          <div class="rit-timeline">
            <div class="rit-point"><div class="rit-val">{int(s['spring_rit'])}</div><div class="rit-label">Spring 25</div></div>
            <div class="rit-arrow">&rarr;</div>
            <div class="rit-point"><div class="rit-val">{fmt_num(s['fall_rit'])}</div><div class="rit-label">Fall 25</div></div>
            <div class="rit-arrow">&rarr;</div>
            <div class="rit-point"><div class="rit-val">{fmt_num(s['winter_rit'])}</div><div class="rit-label">Winter 26</div></div>
          </div>
          <p class="detail-line" style="margin-top:10px;">{slide_str}</p>
        </div>"""
    else:
        yoy_html = f"""
        <div class="metric-card">
          <h3>Year-over-Year</h3>
          <div class="rit-timeline">
            <div class="rit-point muted"><div class="rit-val">&mdash;</div><div class="rit-label">Spring 25</div></div>
            <div class="rit-arrow">&rarr;</div>
            <div class="rit-point"><div class="rit-val">{fmt_num(s['fall_rit'])}</div><div class="rit-label">Fall 25</div></div>
            <div class="rit-arrow">&rarr;</div>
            <div class="rit-point"><div class="rit-val">{fmt_num(s['winter_rit'])}</div><div class="rit-label">Winter 26</div></div>
          </div>
          <p class="detail-line muted" style="margin-top:10px;">No Spring 2025 score available</p>
        </div>"""

    # --- Comments ---
    comments_html = ""
    if s['comments'] and s['comments'].strip():
        comments_html = f"""
        <div class="metric-card">
          <h3>Coach Notes</h3>
          <p class="comment-text">{s['comments']}</p>
        </div>"""

    # --- Full page ---
    page_container_style = "max-width: 960px;"
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{s['name']} - Reading 3+ Results Profile</title>
<style>{SHARED_CSS}</style>
</head>
<body>

<div class="profile-header">
  <div class="container" style="{page_container_style}">
    <div>
      <h1>{s['name']}</h1>
      <div style="font-size:0.85rem; color:rgba(255,255,255,0.75); margin-top:4px;">{s['campus']}</div>
    </div>
    <div class="badges">
      <span class="grade-badge">Grade {s['age_grade'] if s['age_grade'] else '?'}</span>
      <span class="grade-badge">{s['level_display']}</span>
      <span class="grade-badge">HMG {fmt_num(s['hmg'])}</span>
      <span class="grade-badge">RIT {fmt_num(s['fall_rit'])} &rarr; {fmt_num(s['winter_rit'])}</span>
    </div>
  </div>
</div>

<div class="container" style="{page_container_style}">

<div class="nav-bar">
  <div>
    <a href="../index.html" class="nav-link back-link">&larr; Back to Reading 3+ Results</a>
    <span class="position-label">&nbsp;&middot;&nbsp; Student {position} of {total}</span>
  </div>
  <div>
    {prev_link}
    {' &nbsp;|&nbsp; ' if prev_link and next_link else ''}
    {next_link}
  </div>
</div>

<div style="margin-bottom: 16px;">
  {issue_tags}
  {'<span class="tag tag-yellow">Early Lit</span>' if s['early_lit'] else ''}
</div>

<div class="growth-hero">
  <div class="growth-box">
    <div class="big-num {growth_class(s['growth'])}">{growth_display(s['growth'])}</div>
    <div class="label">RIT Growth (F&rarr;W)</div>
  </div>
  <div class="growth-box">
    <div class="big-num {pct_class(s['pct_expected'])}">{fmt_num(s['pct_expected'])}%</div>
    <div class="label">% Expected Time</div>
  </div>
  <div class="growth-box">
    <div class="big-num">{fmt_num(s['pct_instr'])}%</div>
    <div class="label">Instruction XP</div>
  </div>
  <div class="growth-box">
    <div class="big-num">{fmt_num(s['gap'])}</div>
    <div class="label">Grade Gap</div>
  </div>
</div>

<div class="metric-card">
  <h3>Grade</h3>
  <div class="metric-grid">
    <div class="metric">
      <div class="metric-val">{s['age_grade'] if s['age_grade'] else '&mdash;'}</div>
      <div class="metric-label">Age Grade</div>
    </div>
    <div class="metric">
      <div class="metric-val">{fmt_num(s['rit'])}</div>
      <div class="metric-label">R90 Grade</div>
    </div>
    <div class="metric">
      <div class="metric-val">{s['reading_grade'] if s['reading_grade'] else 'N/A'}</div>
      <div class="metric-label">Reading Grade</div>
    </div>
  </div>
</div>

<div class="metric-card">
  <h3>Session Flags</h3>
  <div class="metric-grid">
    <div class="metric"><div class="metric-val">{yes_no_html(s['put_time'])}</div><div class="metric-label">Put in Time?</div></div>
    <div class="metric"><div class="metric-val">{yes_no_html(s['earned_xp_flag'])}</div><div class="metric-label">Earned XP?</div></div>
    <div class="metric"><div class="metric-val">{s['eff_mastered']}</div><div class="metric-label">Grades Mastered</div></div>
    <div class="metric"><div class="metric-val">{yes_no_html(s['mastered_1'])}</div><div class="metric-label">Mastered &ge;1?</div></div>
    <div class="metric"><div class="metric-val">{yes_no_html(s['accuracy_flag'])}</div><div class="metric-label">Accuracy &gt;80%?</div></div>
  </div>
</div>

<div class="two-col">
  <div class="metric-card">
    <h3>Time on Task</h3>
    <div class="metric-grid">
      <div class="metric"><div class="metric-val">{fmt_num(s['total_active_minutes'])}</div><div class="metric-label">Reading Min</div></div>
      <div class="metric"><div class="metric-val">{fmt_num(expected_minutes)}</div><div class="metric-label">Expected Min</div></div>
      <div class="metric"><div class="metric-val {pct_class(s['pct_expected'])}">{fmt_num(s['pct_expected'])}%</div><div class="metric-label">% of Expected</div></div>
      <div class="metric"><div class="metric-val">{fmt_num(s['daily_avg'], 1)}</div><div class="metric-label">Daily Avg Min</div></div>
    </div>
  </div>
  {yoy_html}
</div>

{timeline_html}

{xp_section}

{waste_html}

{test_html}

{comments_html}

</div>

<div class="footer">
  Reading 3+ Results Profile &middot; Winter 2025-26 MAP &middot; Updated Feb 9, 2026
</div>

</body>
</html>"""

    filepath = os.path.join(STUDENTS_DIR, f"{s['slug']}.html")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)


# ============================================================
# MAIN
# ============================================================
def main():
    print("=" * 80)
    print("READING CRM BUILDER")
    print("=" * 80)

    # 1. Load data
    print("\n--- Loading Data ---")
    map_df = load_map_analysis()
    daily_df = load_daily_metrics()
    results_df = load_reading_results()
    spring_df = load_spring_map()

    # 2. School days
    effective_days, expected_minutes, school_day_dates = compute_school_days()
    print(f"\nEffective school days: {effective_days}")
    print(f"Expected reading minutes: {expected_minutes}")

    # 3. Pre-group daily metrics by email
    print("\n--- Pre-grouping daily metrics ---")
    daily_by_email = {email: group for email, group in daily_df.groupby('email')}
    print(f"  {len(daily_by_email)} unique student email groups")

    # Pre-group test results by email
    results_by_email = {email: group for email, group in results_df.groupby('student_email')}
    print(f"  {len(results_by_email)} unique test result email groups")

    # Spring MAP lookup by name
    spring_lookup = {}
    for _, row in spring_df.iterrows():
        student_name = row['Student']
        if pd.notna(student_name):
            spring_lookup[str(student_name).strip()] = row['Spring 2425 RIT']

    # 4. Process each student
    print("\n--- Processing students ---")
    all_students = []
    for _, row in map_df.iterrows():
        email = row['Email']
        name = row['Student Name']
        if pd.isna(name) or pd.isna(email):
            continue

        student_daily = daily_by_email.get(email, pd.DataFrame())
        student_tests = results_by_email.get(email, pd.DataFrame())
        spring_rit = spring_lookup.get(name.strip(), np.nan)

        # Convert school_day_dates to date objects for comparison
        school_dates = [d for d in school_day_dates]

        metrics = compute_student_metrics(
            row, student_daily, student_tests, spring_rit,
            effective_days, expected_minutes, school_dates
        )
        all_students.append(metrics)

    print(f"  Processed {len(all_students)} students")

    # 5. Resolve slug collisions
    resolve_slugs(all_students)
    collision_count = len([s for s in all_students if '_' in s['slug'] and s['slug'].count('_') > 1])
    print(f"  Slug collisions resolved: {collision_count} students needed disambiguation")

    # 6. Sort by growth ascending (worst first)
    all_students.sort(key=lambda s: s['growth'] if s['growth'] is not None else 999)

    # 7. Save JSON
    # Custom serializer for date objects
    def json_serialize(obj):
        if isinstance(obj, (date,)):
            return obj.isoformat()
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        raise TypeError(f"Type {type(obj)} not serializable")

    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(all_students, f, indent=2, default=json_serialize)
    print(f"  Saved {JSON_FILE}")

    # 8. Detect systemic issues
    print("\n--- Detecting systemic issues ---")
    systemic_issues = detect_systemic_issues(all_students)
    for issue in systemic_issues:
        print(f"  #{systemic_issues.index(issue)+1}: {issue['title']} ({issue['count']} students)")

    # 9. Compute campus stats
    campus_groups = defaultdict(list)
    for s in all_students:
        campus_groups[s['campus']].append(s)

    campus_stats = []
    for campus, stu_list in campus_groups.items():
        growths = [s['growth'] for s in stu_list if s['growth'] is not None]
        levels = sorted(set(s['level'] for s in stu_list if s['level']))
        met_2x_count = sum(1 for s in stu_list if s['met_2x'])
        campus_stats.append({
            'campus': campus,
            'count': len(stu_list),
            'levels': ', '.join(levels),
            'avg_growth': round(np.mean(growths), 1) if growths else None,
            'neg_count': sum(1 for g in growths if g < 0),
            'pct_met_2x': round(met_2x_count / len(stu_list) * 100, 1) if len(stu_list) > 0 else 0,
        })

    # 10. Create output directories
    os.makedirs(STUDENTS_DIR, exist_ok=True)

    # 11. Generate dashboard
    print("\n--- Generating HTML ---")
    generate_dashboard(all_students, campus_stats, systemic_issues, effective_days, expected_minutes)

    # 12. Generate student pages
    total = len(all_students)
    for i, student in enumerate(all_students):
        prev_s = all_students[i - 1] if i > 0 else None
        next_s = all_students[i + 1] if i < total - 1 else None
        generate_student_page(student, prev_s, next_s, i + 1, total, expected_minutes)
    print(f"  Generated {total} student pages in {STUDENTS_DIR}")

    print("\n" + "=" * 80)
    print(f"DONE. Dashboard: {OUT_DIR}/index.html")
    print(f"Student pages: {STUDENTS_DIR}/")
    print("=" * 80)


if __name__ == '__main__':
    main()

# Deep Dive Reading Analysis - Changelog & Context for New Model

## Project Summary
Analysis of 21 middle school students at Alpha Austin MS who showed <2x growth on Winter 2025-26 MAP reading test. Goal: understand WHY students aren't growing by examining daily activity, XP earnings, app usage, test history, and year-over-year trajectories.

## Key Dates
- **Analysis Period**: Aug 14, 2025 → Jan 23, 2026 (MAP test date)
- **Effective School Days**: 86 (excludes MAP testing weeks, holidays, breaks)
- **Expected Reading Time**: 25 min/day × 86 days = 2,150 minutes total

---

## Current File Structure

```
/Users/alexandra/Documents/Claude/
├── data daily metrics/
│   └── Daily_Metrics_by_Student_2025-08-13 → 2026-02-25.csv   # NEW - daily granular data
├── data test results/
│   ├── Test School Year.csv                                    # Test submissions (moved)
│   └── reading-results-2026-02-05.csv                          # NEW - detailed test results
├── data other/                                                 # Empty - for future data
├── docs/                                                       # GitHub Pages folder
│   ├── index.html
│   ├── robots.txt                                              # Blocks search engines
│   └── students/*.html                                         # 21 student profiles
├── deep_dive_report/                                           # Original report folder
│   ├── index.html
│   └── students/*.html
├── Combined DeepDive - Low_No Growth Alpha Austin MS Winter 25-26 - Retakes G3+.csv
├── Combined DeepDive - Low_No Growth Alpha Austin MS Winter 25-26 - Weekly XP per Student_Subject - All.csv
├── Combined DeepDive - Low_No Growth Alpha Austin MS Winter 25-26 - Weekly minutes per student_subject - All.csv
├── Last Years Spring MAP Scores.csv
├── deep_dive_data.json                                         # Generated student data for HTML
├── analyze_low_growth.py                                       # Main analysis script
├── anonymize_and_regenerate.py                                 # Anonymization script
├── generate_student_pages.py                                   # HTML generator
└── .gitignore                                                  # Excludes CSVs, PDFs, JSON from git
```

---

## GitHub Repository

- **Repo**: https://github.com/alexwrega/reading-deep-dive
- **Live Site**: https://alexwrega.github.io/reading-deep-dive/
- **Privacy**: robots.txt blocks search engine indexing
- **Anonymization**: Student names shown as "First Name + Last Initial" (e.g., "Love L.")

---

## Critical Domain Knowledge (User-Provided Rules)

### App Categorization
| Category | Apps | Purpose |
|----------|------|---------|
| **Instruction** (G3+) | Alpha Read, MobyMax (G3-G8 only) | Learning/teaching |
| **Testing** | Mastery Track, 100x100, Alpha Tests | Assessment (NOT learning!) |
| **Early Literacy** (<G3) | Anton, ClearFluency, Amplify, Mentava, Literably, Lalilo, Lexia Core5, FastPhonics, TeachTales | May be appropriate if student hasn't passed G3 tests |
| **Admin/Other** | Manual XP Assign, Timeback UI, TimeBack Dash, Acely SAT | Not instructional |

### Key Rules
1. **"Testing ≠ Learning"** - If a student spends too much time on tests, they are NOT learning
2. **MobyMax caps at G8** - Students who master G8+ have NO reading instruction app (systemic gap)
3. **Reading only** - Analysis focuses on Reading, not Language
4. **Effective Test** - A test submission that counts as productive progress
5. **Doom Loop** - Student stuck retaking same grade test 3+ times

### User Hypotheses (Confirmed)
- Students at/ahead of grade (gap ≤ 0) lack motivation
- Students 3+ grades behind are overwhelmed
- Mid-semester enrollees: Kanhai Shah, Bobbi Brown (no spring MAP, late first test dates)

---

## Top 3 Issues Identified

### 1. No Instruction App for G9+ Students
- **5 students** beyond MobyMax ceiling (avg growth: -5.0)
- **3 students** in MobyMax range but not assigned (avg growth: -3.7)
- Affected: Love L., Eddie M., Parker C., Roarke R., Nadine R. (beyond); Kanhai S., Jack B., Valentina M. (should have)

### 2. Over-Testing & Doom Loops
- **2 students** severely over-testing (>50% XP from tests): Gwendolyn M. (70%), Sam R. (58%)
- **3 students** in doom loops: Elena M. (G6), Gwendolyn M. (G7), Sam R. (G5)
- **14 of 20** tested students have <50% effective test rate

### 3. Minutes ≠ Growth
- **11 of 21** met the 2,150-minute target
- **9 of those 11** still had NEGATIVE growth
- Correlation: minutes vs growth r = -0.17 (not significant)

---

## Key Metrics & Findings

| Metric | Value |
|--------|-------|
| Total students analyzed | 21 |
| Average growth | -2.9 RIT |
| Students with negative growth | 16/21 |
| Students with 0 growth | 2/21 |
| Students with positive growth | 3/21 (all +1 RIT) |
| Met time target (100%+) | 11/21 |
| Met time but declined | 9/11 |
| Minutes vs Growth correlation | r = -0.17 (not significant) |
| XP vs Growth correlation | r = 0.44, p = 0.048 (weakly significant) |

---

## What's Been Completed

1. ✅ Loaded and analyzed all CSV data files
2. ✅ Calculated effective school days from calendar (86 days)
3. ✅ Built 9 analyses: Time on Task, XP Breakdown, Correlations, Gaming/Waste Detection, Comments Cross-Reference, Peer Comparison, Student Clustering, Test History, Year-over-Year
4. ✅ Generated executive summary HTML with top 3 issues
5. ✅ Generated 21 individual student profile HTML pages
6. ✅ Anonymized names (First + Last Initial)
7. ✅ Published to GitHub with GitHub Pages
8. ✅ Added robots.txt to prevent search indexing

---

## What's Next (User Intent)

User wants to **expand this into a bigger project** with:
1. **More datasets** - New files added to `data daily metrics/` and `data test results/`
2. **Explainer text file** - User will add context/data dictionary
3. **More precise analysis** - Using daily granular data instead of weekly aggregates
4. **Potential Vercel deployment** - For password protection later

---

## New Data Files to Explore

### 1. `data daily metrics/Daily_Metrics_by_Student_2025-08-13 → 2026-02-25.csv`
- ~6.5MB - likely daily per-student metrics
- Could enable: weekly trends, engagement patterns, day-of-week analysis

### 2. `data test results/reading-results-2026-02-05.csv`
- ~2.4MB - likely detailed test result data
- Could enable: better doom loop detection, test timing analysis, per-question analysis

---

## Technical Notes

- **Git**: Using Homebrew git (`/usr/local/bin/git`) due to broken Xcode CLI tools
- **Python**: Scripts use pandas, scipy (installed via pip3)
- **Calendar PDF**: `Alpha School 2025-2026 Calendar.pdf` was used but excluded from git

---

## Commands to Resume

```bash
# Navigate to project
cd /Users/alexandra/Documents/Claude

# Check git status
/usr/local/bin/git status

# Run analysis script
python3 analyze_low_growth.py

# Regenerate anonymized HTML
python3 anonymize_and_regenerate.py

# Push changes
/usr/local/bin/git add . && /usr/local/bin/git commit -m "message" && /usr/local/bin/git push
```

---

*Generated: Feb 6, 2026*

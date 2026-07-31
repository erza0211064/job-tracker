# -*- coding: utf-8 -*-
"""
每日職缺自動追蹤與篩選系統 (Job Tracker Cron Job)
"""
import os
import sqlite3
import pandas as pd
from datetime import datetime, timedelta

DB_PATH = "job_tracker.db"
HISTORICAL_CSV_PATH = "job_tracker_export_2026-07-24.csv"
OUTPUT_REPORT_DIR = "daily_reports"

TARGET_KEYWORDS = {
    'primary': ['Quality', 'QA', 'Software QA', 'Test Engineer', 'Quality Manager'],
    'skills': ['Robotics', 'Automation', 'AI', 'Hardware', 'Integration', 'Python', 'Linux', 'FMCW', 'Lidar']
}

def init_db(db_path=DB_PATH, csv_path=HISTORICAL_CSV_PATH):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tracked_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT,
            title TEXT,
            applied_date TEXT,
            status TEXT,
            salary TEXT,
            job_url TEXT UNIQUE,
            jd_description TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
        inserted_count = 0
        for _, row in df.iterrows():
            url = row.get('職缺網址')
            if pd.isna(url) or not str(url).strip():
                continue
            try:
                cursor.execute("""
                    INSERT INTO tracked_jobs (company, title, applied_date, status, salary, job_url, jd_description, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(row.get('公司名稱', '')),
                    str(row.get('職務名稱', '')),
                    str(row.get('投遞日期', '')),
                    str(row.get('狀態', '已記錄')),
                    str(row.get('薪資待遇', '')),
                    str(url),
                    str(row.get('完整JD說明', '')),
                    str(row.get('筆記備註', ''))
                ))
                inserted_count += 1
            except sqlite3.IntegrityError:
                pass
        conn.commit()
        print(f"[DB Init] 歷史 CSV 匯入完成，成功寫入 {inserted_count} 筆新職缺。")
    conn.close()

def calculate_match_score(title, jd_text):
    text = (str(title) + " " + str(jd_text)).lower()
    score = 0
    matched_tags = []
    for kw in TARGET_KEYWORDS['primary']:
        if kw.lower() in text:
            score += 3
            matched_tags.append(kw)
    for kw in TARGET_KEYWORDS['skills']:
        if kw.lower() in text:
            score += 2
            matched_tags.append(kw)
    return score, list(set(matched_tags))

def get_existing_urls(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT job_url FROM tracked_jobs WHERE job_url IS NOT NULL")
    urls = set(row[0] for row in cursor.fetchall())
    conn.close()
    return urls

def run_daily_job_tracker():
    today_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{today_now}] 開始執行每日職缺自動追蹤與篩選系統...")
    init_db()
    existing_urls = get_existing_urls()
    print(f"[De-duplication] 當前 SQLite DB 中已記錄 {len(existing_urls)} 筆職缺連結。")
    conn = sqlite3.connect(DB_PATH)
    query = "SELECT company, title, applied_date, status, salary, job_url, jd_description FROM tracked_jobs"
    df = pd.read_sql_query(query, conn)
    conn.close()
    results = []
    for idx, row in df.iterrows():
        score, tags = calculate_match_score(row['title'], row['jd_description'])
        salary_val = str(row['salary'])
        if salary_val == 'nan' or not salary_val.strip():
            salary_val = '未提供'
        results.append({
            '公司名稱': row['company'],
            '職務名稱': row['title'],
            '投遞狀態': row['status'],
            '薪資待遇': salary_val,
            '匹配得分': score,
            '技能標籤': ', '.join(tags),
            '職缺網址': row['job_url']
        })
    res_df = pd.DataFrame(results).sort_values(by='匹配得分', ascending=False)
    os.makedirs(OUTPUT_REPORT_DIR, exist_ok=True)
    today_str = datetime.now().strftime("%Y-%m-%d")
    output_csv = os.path.join(OUTPUT_REPORT_DIR, f"filtered_jobs_{today_str}.csv")
    res_df.to_csv(output_csv, index=False, encoding="utf-8-sig")
    output_md = os.path.join(OUTPUT_REPORT_DIR, f"daily_summary_{today_str}.md")
    with open(output_md, "w", encoding="utf-8") as f:
        f.write(f"# 每日職缺自動追蹤與篩選報告 ({today_str})\n\n")
        f.write(f"- **執行時間**：{today_now}\n")
        f.write(f"- **總記錄職缺數**：{len(res_df)} 筆\n\n")
        f.write("### 🎯 高匹配度職缺推薦列表\n\n")
        f.write(res_df.head(10).to_markdown(index=False))
        f.write("\n\n---\n*報告由 Job Tracker Cron Job 自動生成*\n")
    print(f"[Done] 產出報告完成：\n  - CSV: {output_csv}\n  - Markdown: {output_md}")

if __name__ == "__main__":
    run_daily_job_tracker()
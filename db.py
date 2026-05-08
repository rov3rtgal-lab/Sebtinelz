import sqlite3
import os


def init_db():
    if not os.path.exists('instance'):
        os.makedirs('instance')

    conn = sqlite3.connect('instance/sentinel.db')
    cursor = conn.cursor()

    # 1. Table para sa Companies (Para sa Blacklisting)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS company (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            sec_id TEXT UNIQUE,
            type TEXT,            -- OJT, Overseas, o Scholar
            status TEXT DEFAULT 'Active',
            compliance_score INTEGER DEFAULT 100,
            industry TEXT         -- Tech, BPO, Hospitality, etc.
        )
    ''')

    # 2. Table para sa Incident Reports (Para sa "Report an Incident" button)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            complainant_name TEXT,
            issue_type TEXT,      -- Harassment, Violation, etc.
            description TEXT,
            status TEXT DEFAULT 'Pending', -- Pending, Under Review, Resolved
            FOREIGN KEY(company_id) REFERENCES company(id)
        )
    ''')

    # 3. Table para sa Overseas Scholars (Para sa "Overseas Scholar Pathways")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scholarships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            program_name TEXT,
            country TEXT,
            employer_name TEXT,
            accreditation_status TEXT DEFAULT 'Certified Safe'
        )
    ''')

    # Add this inside the init_db() function in db.py

    # 4. Table para sa Users
    cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_type TEXT NOT NULL,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                birthdate TEXT NOT NULL,
                gender TEXT,
                contact TEXT NOT NULL,
                address TEXT,
                pwd_id TEXT,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL, -- In production, use hashed passwords!
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    # Initial Data base sa images
    cursor.execute("SELECT COUNT(*) FROM company")
    if cursor.fetchone()[0] == 0:
        sample_companies = [
            ('Tech Pioneers Corp', 'SEC/0003008', 'Scholarship Partner', 'Active', 95, 'Tech'),
            ('Industrial Solutions', 'SEC/0003009', 'Local OJT', 'Blacklisted', 40, 'BPO'),
            ('Global Japan STEM', 'SEC/0003010', 'Overseas Scholar', 'Active', 88, 'Hospitality')
        ]
        cursor.executemany(
            "INSERT INTO company (name, sec_id, type, status, compliance_score, industry) VALUES (?,?,?,?,?,?)",
            sample_companies)

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("Database Initialized with all tables!")
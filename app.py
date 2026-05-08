import requests
from flask import request, jsonify
from flask import Flask, request, jsonify

from flask import redirect, url_for

import os
import io
import requests
import numpy as np
from flask import Flask, render_template, request, redirect, url_for, send_file, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from reportlab.pdfgen import canvas
from sklearn.neighbors import NearestNeighbors

app = Flask(__name__)
app.secret_key = "sentinel_secret_key"

# --- DATABASE CONFIGURATION ---
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'instance', 'sentinel.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# login form
@app.route('/')
def index():
    return redirect(url_for('login'))

# admin email and pass

ADMIN_EMAIL    = "admin@sentinel.gov.ph"
ADMIN_PASSWORD = "sentinel2025"   # ← change this

# ── ADMIN login page ─────────────────────────────────────────
@app.route('/admin-login', methods=['GET'])
def admin_login_page():
    return render_template('admin_login.html')


@app.route('/admin-login', methods=['POST'])
def admin_login_action():
    """Handles the admin login form submission."""
    email    = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()

    if email == ADMIN_EMAIL and password == ADMIN_PASSWORD:
        # ✅ Credentials match → go to admin dashboard
        return redirect(url_for('admin_dashboard'))

    # ❌ Wrong credentials → flash error, stay on admin login
    flash("Invalid admin credentials. Please try again.")
    return redirect(url_for('admin_login_page'))


# ============================================================
# DATABASE MODELS
# ============================================================

class Company(db.Model):
    id               = db.Column(db.Integer, primary_key=True)
    name             = db.Column(db.String(100), nullable=False)
    sec_id           = db.Column(db.String(50), unique=True)
    industry         = db.Column(db.String(50))
    status           = db.Column(db.String(20), default='Active')
    compliance_score = db.Column(db.Integer, default=100)
    type             = db.Column(db.String(50))
    skills_vector    = db.Column(db.String(50), default="0,0,0,0")


class Lawyer(db.Model):
    id             = db.Column(db.Integer, primary_key=True)
    name           = db.Column(db.String(100), nullable=False)
    specialization = db.Column(db.String(100))
    is_available   = db.Column(db.Boolean, default=True)


class IncidentReport(db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    incident_type = db.Column(db.String(100))
    company_name  = db.Column(db.String(100))
    description   = db.Column(db.Text)
    is_anonymous  = db.Column(db.Boolean, default=False)
    status        = db.Column(db.String(20), default='Pending')


class LegalAidRequest(db.Model):
    id               = db.Column(db.Integer, primary_key=True)
    fullname         = db.Column(db.String(150))
    email            = db.Column(db.String(150))
    contact          = db.Column(db.String(50))
    concern_type     = db.Column(db.String(100), default='Other')
    company_involved = db.Column(db.String(150))
    concern          = db.Column(db.Text)
    is_anonymous     = db.Column(db.Boolean, default=False)
    status           = db.Column(db.String(50), default='Pending')


# ============================================================
# MACHINE LEARNING LOGIC
# ============================================================

def get_ml_recommendations(user_profile, company_list):
    if not company_list or len(company_list) < 1:
        return []
    features = []
    valid_companies = []
    for co in company_list:
        try:
            vector = [int(x) for x in co.skills_vector.split(',')]
            features.append(vector)
            valid_companies.append(co)
        except (ValueError, AttributeError):
            continue
    if not features:
        return []
    features_array = np.array(features)
    k_value = min(len(features_array), 3)
    model = NearestNeighbors(n_neighbors=k_value, metric='cosine')
    model.fit(features_array)
    _, indices = model.kneighbors([user_profile])
    return [valid_companies[i] for i in indices[0]]


# ============================================================
# AUTH & DASHBOARD ROUTES
# ============================================================

@app.route('/login', methods=['GET'])
def login():
    return render_template('login.html')


@app.route('/login_action', methods=['POST'])
def login_action():
    role     = request.form.get('role')
    email    = request.form.get('email')
    password = request.form.get('password')

    # Basic check (replace with real DB lookup later)
    if role == 'admin':
        return redirect(url_for('admin_dashboard'))
    else:
        return redirect(url_for('user_dashboard'))


@app.route('/user')
def user_dashboard():
    safe_companies = Company.query.filter_by(status='Active').all()
    blacklisted    = Company.query.filter_by(status='Blacklisted').all()
    return render_template('user.html', safe=safe_companies, banned=blacklisted)


# ============================================================
# USER SERVICE ROUTES
# ============================================================

@app.route('/service/ojt')
def ojt_view():
    results         = Company.query.filter_by(type='Local OJT', status='Active').all()
    student_vector  = [1, 0, 0, 1]
    recommendations = get_ml_recommendations(student_vector, results)
    return render_template('ojt_placements.html', results=results, recommendations=recommendations)


@app.route('/service/pwd-jobs')
def pwd_view():
    results         = Company.query.filter_by(type='Overseas', status='Active').all()
    pwd_vector      = [1, 0, 1, 0]
    recommendations = get_ml_recommendations(pwd_vector, results)
    return render_template('pwd_overseas.html', results=results, recommendations=recommendations)


@app.route('/service/scholar-pathway')
def scholar_view():
    results = Company.query.filter_by(type='Scholarship', status='Active').all()
    return render_template('scholar_pathways.html', results=results)


@app.route('/rights')
def rights_view():
    rights_content = [
        {"title": "PWD Protection Act",  "desc": "RA 10524: Mandatory reservation of positions for PWDs."},
        {"title": "Intern Rights",        "desc": "8-hour work limits and mandatory safety insurance for OJT."},
        {"title": "Overseas Safety",      "desc": "Passport retention rights and 24/7 embassy support access."}
    ]
    return render_template('rights_portal.html', content=rights_content)


# ============================================================
# PAO / LEGAL AID ROUTES (User-Facing)
# ============================================================

@app.route('/pao')
def pao_portal():
    return render_template('access_pao.html')


@app.route('/admin/pao')
def admin_pao_view():
    return render_template('access_pao.html')


@app.route('/request-legal-aid', methods=['GET', 'POST'])
def request_legal_aid():
    if request.method == 'POST':
        fullname         = request.form.get('fullname', '').strip()
        email            = request.form.get('email', '').strip()
        contact          = request.form.get('contact', '').strip()
        concern_type     = request.form.get('concern_type', 'Other').strip()
        company_involved = request.form.get('company_involved', '').strip()
        concern          = request.form.get('concern', '').strip()
        is_anonymous     = True if request.form.get('is_anonymous') else False

        # Fallback: if concern_type came in blank, default it
        if not concern_type:
            concern_type = 'Other'

        new_req = LegalAidRequest(
            fullname         = fullname,
            email            = email,
            contact          = contact,
            concern_type     = concern_type,
            company_involved = company_involved,
            concern          = concern,
            is_anonymous     = is_anonymous,
            status           = 'Pending'
        )
        db.session.add(new_req)
        db.session.commit()

        print(f"[SENTINEL] Legal Aid Saved → ID={new_req.id} | Name={new_req.fullname} | Type={new_req.concern_type}")

        flash("Your legal aid application has been submitted. A PAO attorney will be assigned to your case within 3–5 working days.")
        return redirect(url_for('pao_portal'))

    return redirect(url_for('pao_portal'))


# ============================================================
# SHARED UTILITIES
# ============================================================

@app.route('/search')
def search():
    query   = request.args.get('q', '')
    results = Company.query.filter(Company.name.contains(query), Company.status == 'Active').all()
    return render_template('ojt_placements.html', results=results, query=query)


@app.route('/report')
def report_page():
    companies = Company.query.filter_by(status='Active').all()
    return render_template('report.html', companies=companies)


@app.route('/submit-report', methods=['POST'])
def handle_report():
    new_report = IncidentReport(
        incident_type = request.form.get('incident_type'),
        company_name  = request.form.get('company_name'),
        description   = request.form.get('description'),
        is_anonymous  = True if request.form.get('is_anonymous') else False,
        status        = 'Pending'
    )
    db.session.add(new_report)
    db.session.commit()
    flash("Report successfully submitted to Sentinel.")
    return redirect(url_for('user_dashboard'))


# ============================================================
# AI CHATBOT ROUTE
# ============================================================

def search_courtlistener(query, max_results=3):
    """
    Searches CourtListener for opinions/cases matching the query.
    Returns a list of dicts with title, court, date, and snippet.
    """
    url    = "https://www.courtlistener.com/api/rest/v4/search/"
    params = {"q": query, "type": "o"}          # "o" = opinions (case law)

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data    = resp.json()
        results = data.get("results", [])[:max_results]

        cases = []
        for r in results:
            cases.append({
                "title":   r.get("caseName")    or r.get("case_name", "Untitled Case"),
                "court":   r.get("court")       or r.get("court_id", "Unknown Court"),
                "date":    r.get("dateFiled")   or r.get("date_filed", "N/A"),
                "snippet": (r.get("snippet") or "No summary available.")[:300],
                "url":     f"https://www.courtlistener.com{r['absolute_url']}" if r.get("absolute_url") else "#"
            })
        return cases

    except requests.exceptions.Timeout:
        return None   # signals timeout
    except Exception as e:
        app.logger.error(f"CourtListener error: {e}")
        return []


# ============================================================
# KEYWORD EXTRACTOR  —  maps user concern to search terms
# ============================================================

KEYWORD_MAP = {
    "harassment":       "workplace harassment gender Safe Spaces Act",
    "harassed":         "workplace harassment gender Safe Spaces Act",
    "safe spaces":      "Safe Spaces Act RA 11313 harassment",
    "ra 11313":         "RA 11313 Safe Spaces Act gender harassment",
    "pwd":              "PWD employment disability discrimination RA 10524",
    "disability":       "disability employment discrimination PWD Philippines",
    "ra 10524":         "RA 10524 PWD employment disability",
    "ojt":              "OJT student intern labor rights Philippines",
    "intern":           "student intern rights overtime hazardous work",
    "overtime":         "overtime pay labor standards Philippines DOLE",
    "unpaid":           "unpaid wages labor Philippines DOLE",
    "wages":            "unpaid wages minimum wage labor Philippines",
    "overseas":         "overseas worker OFW rights migrant passport",
    "ofw":              "OFW migrant worker rights contract Philippines",
    "passport":         "passport confiscation overseas worker illegal",
    "illegal recruitment": "illegal recruitment POEA overseas Philippines",
    "termination":      "illegal dismissal termination labor Philippines",
    "fired":            "illegal dismissal termination labor Philippines",
    "discrimination":   "employment discrimination labor Philippines",
    "sexual harassment":"sexual harassment workplace RA 11313 Philippines",
}

def extract_search_query(user_msg):
    """
    Checks the user message for known keywords and returns
    the best CourtListener search string. Falls back to the raw message.
    """
    msg_lower = user_msg.lower()
    for keyword, search_term in KEYWORD_MAP.items():
        if keyword in msg_lower:
            return search_term
    # Fallback: use the raw message (trimmed to 80 chars)
    return user_msg[:80]


# ============================================================
# RESPONSE BUILDER  —  formats cases into a chat reply
# ============================================================

def build_reply(user_msg, cases):
    """Turns a list of case dicts into a friendly chat message (HTML-safe)."""

    # ── Built-in static guidance for common Philippine law topics ──
    guidance = ""
    msg_lower = user_msg.lower()

    if any(w in msg_lower for w in ["harassment", "harassed", "safe spaces", "ra 11313", "sexual"]):
        guidance = (
            "⚖️ <b>RA 11313 – Safe Spaces Act:</b> Your employer is legally required to act on "
            "your complaint within <b>10 days</b>. A Committee on Decorum and Investigation (CODI) "
            "must exist in every workplace. You cannot be penalized for reporting.<br><br>"
        )
    elif any(w in msg_lower for w in ["pwd", "disability", "ra 10524"]):
        guidance = (
            "♿ <b>RA 10524 – PWD Employment Act:</b> Companies with 100+ employees must reserve "
            "at least <b>1% of positions</b> for PWDs. Refusing employment due to disability alone "
            "is unlawful. Equal pay and reasonable accommodations are required.<br><br>"
        )
    elif any(w in msg_lower for w in ["ojt", "intern", "trainee"]):
        guidance = (
            "🎓 <b>DOLE OJT Guidelines:</b> Interns may not work more than <b>8 hours/day</b>, "
            "cannot be assigned hazardous tasks, and must have safety insurance. "
            "A Memorandum of Agreement between your school and company is mandatory.<br><br>"
        )
    elif any(w in msg_lower for w in ["overseas", "ofw", "passport", "abroad"]):
        guidance = (
            "🌏 <b>RA 10022 – Migrant Workers Act:</b> Your employer abroad <b>cannot hold your "
            "passport</b>. You have the right to contact the Philippine Embassy / POLO 24/7. "
            "Only POEA-accredited agencies may legally deploy workers overseas.<br><br>"
        )
    elif any(w in msg_lower for w in ["unpaid", "wages", "salary", "overtime"]):
        guidance = (
            "💼 <b>Labor Standards (Labor Code):</b> Unpaid wages and illegal overtime are "
            "violations enforceable by DOLE. You may file a complaint at the nearest DOLE "
            "Regional Office or call the DOLE hotline: <b>1349</b>.<br><br>"
        )

    # ── Format CourtListener case results ──
    if not cases:
        case_section = (
            "No related case law was found in the CourtListener database for your query. "
            "This may be because CourtListener primarily indexes U.S. case law. "
            "For Philippine-specific cases, consult the <b>Supreme Court E-Library</b> at "
            "<a href='https://elibrary.judiciary.gov.ph' target='_blank'>elibrary.judiciary.gov.ph</a>."
        )
    else:
        case_lines = []
        for i, c in enumerate(cases, 1):
            case_lines.append(
                f"<b>{i}. {c['title']}</b><br>"
                f"🏛 {c['court']} &nbsp;|&nbsp; 📅 {c['date']}<br>"
                f"{c['snippet']}<br>"
                f"<a href='{c['url']}' target='_blank' style='font-size:0.8rem;'>View full case →</a>"
            )
        case_section = (
            "📚 <b>Related Case Law (via CourtListener):</b><br><br>"
            + "<hr style='margin:8px 0;'>".join(case_lines)
        )

    disclaimer = (
        "<br><br><small style='color:#9e9e9e;'>⚠️ This is general guidance, not formal legal advice. "
        "Consult a PAO lawyer at <a href='/pao'>/pao</a> for case-specific filings.</small>"
    )

    return guidance + case_section + disclaimer


# ============================================================
# CHATBOT ROUTE  —  replace the old /chatbot in app.py
# ============================================================

@app.route('/chatbot', methods=['POST'])
def chatbot_response():
    data     = request.get_json()
    user_msg = (data.get("message") or "").strip()

    if not user_msg:
        return jsonify({"reply": "Please type a question so I can help you."})

    # 1. Map the user's message to a useful search query
    search_query = extract_search_query(user_msg)

    # 2. Fetch related cases from CourtListener
    cases = search_courtlistener(search_query)

    # 3. Handle timeout
    if cases is None:
        return jsonify({
            "reply": (
                "⚠️ The legal search service is taking too long to respond. "
                "Please try again in a moment, or check the "
                "<a href='/rights'>Rights Portal</a> for direct legal guidance."
            )
        })

    # 4. Build and return the formatted reply
    reply = build_reply(user_msg, cases)
    return jsonify({"reply": reply})


# ============================================================
# LAW SEARCH API ROUTE  —  kept as-is, merged into main app
# ============================================================

@app.route('/search-law')
def search_law_api():
    query = (request.args.get("q") or "").strip()
    if not query:
        return jsonify({"error": "Query parameter 'q' is required."}), 400

    url      = "https://www.courtlistener.com/api/rest/v4/search/"
    params   = {"q": query, "type": "o"}

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        return jsonify(resp.json())
    except requests.exceptions.Timeout:
        return jsonify({"error": "CourtListener search timed out."}), 504
    except Exception as e:
        app.logger.error(f"CourtListener /search-law error: {e}")
        return jsonify({"error": "Law search service unavailable."}), 502

# ============================================================
# DEBUG ROUTE (remove in production)
# ============================================================

@app.route('/debug/legal-requests')
def debug_legal_requests():
    reqs = LegalAidRequest.query.all()
    return jsonify([{
        'id':               r.id,
        'fullname':         r.fullname,
        'email':            r.email,
        'contact':          r.contact,
        'concern_type':     r.concern_type,
        'company_involved': r.company_involved,
        'concern':          r.concern,
        'is_anonymous':     r.is_anonymous,
        'status':           r.status
    } for r in reqs])


# ============================================================
# ADMIN DASHBOARD
# ============================================================

@app.route('/admin')
def admin_dashboard():
    all_cos = Company.query.all()
    stats = {
        'pending':     IncidentReport.query.filter_by(status='Pending').count(),
        'blacklisted': Company.query.filter_by(status='Blacklisted').count(),
        'resolved':    IncidentReport.query.filter_by(status='Resolved').count()
    }
    return render_template('admin.html', companies=all_cos, stats=stats)


@app.route('/toggle_blacklist/<int:id>')
def toggle_blacklist(id):
    co = Company.query.get_or_404(id)
    if co.status == 'Active':
        co.status           = 'Blacklisted'
        co.compliance_score = 30
    else:
        co.status           = 'Active'
        co.compliance_score = 95
    db.session.commit()
    return redirect(url_for('admin_dashboard'))


@app.route('/generate_pdf/<int:id>')
def generate_pdf(id):
    co     = Company.query.get_or_404(id)
    buffer = io.BytesIO()
    p      = canvas.Canvas(buffer)
    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, 800, "PROJECT SENTINEL - COMPLIANCE NOTICE")
    p.setFont("Helvetica", 12)
    p.drawString(100, 770, f"Company: {co.name}")
    p.drawString(100, 755, f"SEC/Permit #: {co.sec_id}")
    p.drawString(100, 740, f"Current Status: {co.status}")
    p.drawString(100, 725, f"Compliance Score: {co.compliance_score}/100")
    p.line(100, 715, 500, 715)
    p.drawString(100, 700, "Official record of DOLE/Sentinel agency standing.")
    p.showPage()
    p.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"Notice_{co.name}.pdf")


# ============================================================
# ADMIN — OVERVIEW
# ============================================================

@app.route('/admin/overview')
def admin_overview():
    stats = {
        'pending':     IncidentReport.query.filter_by(status='Pending').count(),
        'blacklisted': Company.query.filter_by(status='Blacklisted').count(),
        'resolved':    IncidentReport.query.filter_by(status='Resolved').count(),
        'active':      Company.query.filter_by(status='Active').count(),
    }
    recent_reports = IncidentReport.query.order_by(IncidentReport.id.desc()).limit(10).all()
    return render_template('admin/overview.html', stats=stats, recent=recent_reports)


# ============================================================
# ADMIN — HEATMAP
# ============================================================

@app.route('/admin/heatmap')
def admin_heatmap():
    heatmap_points = [
        {"lat": 14.5995, "lng": 120.9842, "weight": 8,  "label": "Manila CBD"},
        {"lat": 14.6760, "lng": 121.0437, "weight": 5,  "label": "Quezon City"},
        {"lat": 14.5547, "lng": 121.0244, "weight": 3,  "label": "Makati"},
        {"lat": 10.3157, "lng": 123.8854, "weight": 6,  "label": "Cebu City"},
        {"lat": 7.0731,  "lng": 125.6128, "weight": 4,  "label": "Davao"},
        {"lat": 16.4023, "lng": 120.5960, "weight": 2,  "label": "Baguio"},
        {"lat": 14.8527, "lng": 120.8169, "weight": 3,  "label": "Angeles"},
        {"lat": 10.6840, "lng": 122.9567, "weight": 5,  "label": "Iloilo"},
        {"lat": 8.4822,  "lng": 124.6472, "weight": 2,  "label": "Cagayan de Oro"},
        {"lat": 13.1391, "lng": 123.7438, "weight": 1,  "label": "Legazpi"},
    ]
    incident_count = IncidentReport.query.count()
    return render_template('admin/heatmap.html', heatmap_points=heatmap_points, incident_count=incident_count)


# ============================================================
# ADMIN — COMPANY REGISTRY
# ============================================================

@app.route('/admin/company-registry')
def admin_company_registry():
    companies = Company.query.all()
    return render_template('admin/company_registry.html', companies=companies)


@app.route('/admin/company-registry/add', methods=['POST'])
def admin_add_company():
    new_co = Company(
        name             = request.form.get('name'),
        sec_id           = request.form.get('sec_id'),
        industry         = request.form.get('industry'),
        type             = request.form.get('type'),
        compliance_score = int(request.form.get('compliance_score', 100)),
        skills_vector    = request.form.get('skills_vector', '0,0,0,0'),
        status           = 'Active'
    )
    db.session.add(new_co)
    db.session.commit()
    flash("Company added successfully.", "success")
    return redirect(url_for('admin_company_registry'))


@app.route('/admin/company-registry/edit/<int:id>', methods=['POST'])
def admin_edit_company(id):
    co               = Company.query.get_or_404(id)
    co.name          = request.form.get('name', co.name)
    co.industry      = request.form.get('industry', co.industry)
    co.type          = request.form.get('type', co.type)
    co.compliance_score = int(request.form.get('compliance_score', co.compliance_score))
    db.session.commit()
    flash("Company updated.", "success")
    return redirect(url_for('admin_company_registry'))


@app.route('/admin/company-registry/delete/<int:id>')
def admin_delete_company(id):
    co = Company.query.get_or_404(id)
    db.session.delete(co)
    db.session.commit()
    flash("Company removed from registry.", "warning")
    return redirect(url_for('admin_company_registry'))


@app.route('/admin/company-registry/toggle/<int:id>')
def admin_toggle_blacklist(id):
    co = Company.query.get_or_404(id)
    if co.status == 'Active':
        co.status           = 'Blacklisted'
        co.compliance_score = max(co.compliance_score - 30, 10)
    else:
        co.status           = 'Active'
        co.compliance_score = min(co.compliance_score + 30, 100)
    db.session.commit()
    flash(f"'{co.name}' status updated to {co.status}.", "info")
    return redirect(url_for('admin_company_registry'))


# ============================================================
# ADMIN — PENDING INCIDENTS
# ============================================================

@app.route('/admin/pending-incidents')
def admin_pending_incidents():
    pending = IncidentReport.query.filter_by(status='Pending').order_by(IncidentReport.id.desc()).all()
    return render_template('admin/pending_incidents.html', incidents=pending)


@app.route('/admin/pending-incidents/resolve/<int:id>')
def admin_resolve_incident(id):
    report        = IncidentReport.query.get_or_404(id)
    report.status = 'Resolved'
    db.session.commit()
    flash("Incident marked as Resolved.", "success")
    return redirect(url_for('admin_pending_incidents'))


@app.route('/admin/pending-incidents/archive/<int:id>')
def admin_archive_incident(id):
    report        = IncidentReport.query.get_or_404(id)
    report.status = 'Archived'
    db.session.commit()
    flash("Incident archived.", "warning")
    return redirect(url_for('admin_pending_incidents'))


# ============================================================
# ADMIN — UHT REPORTS
# ============================================================

@app.route('/admin/uht-reports')
def admin_uht_reports():
    from collections import defaultdict
    all_reports = IncidentReport.query.all()
    grouped     = defaultdict(list)
    by_company  = defaultdict(int)
    for r in all_reports:
        grouped[r.incident_type or 'Unclassified'].append(r)
        by_company[r.company_name or 'Unknown'] += 1
    return render_template('admin/uht_reports.html',
                           grouped    = dict(grouped),
                           by_company = dict(by_company),
                           total      = len(all_reports))


# ============================================================
# ADMIN — DOLE VERIFICATION
# ============================================================

@app.route('/admin/dole-verification')
def admin_dole_verification():
    needs_verification = Company.query.filter(Company.compliance_score < 90).all()
    verified           = Company.query.filter(Company.compliance_score >= 90).all()
    return render_template('admin/dole_verification.html',
                           needs_verification = needs_verification,
                           verified           = verified)


@app.route('/admin/dole-verification/verify/<int:id>')
def admin_verify_company(id):
    co = Company.query.get_or_404(id)
    co.compliance_score = min(co.compliance_score + 15, 100)
    db.session.commit()
    flash(f"'{co.name}' verified. Score updated to {co.compliance_score}/100.", "success")
    return redirect(url_for('admin_dole_verification'))


# ============================================================
# ADMIN — OVERSEAS (DMW)
# ============================================================

@app.route('/admin/overseas')
def admin_overseas():
    overseas  = Company.query.filter_by(type='Overseas').all()
    high_risk = [c for c in overseas if c.compliance_score < 70]
    compliant = [c for c in overseas if c.compliance_score >= 70]
    return render_template('admin/overseas.html',
                           overseas  = overseas,
                           high_risk = high_risk,
                           compliant = compliant)


# ============================================================
# ADMIN — SCHOLARSHIPS
# ============================================================

@app.route('/admin/scholarships')
def admin_scholarships():
    scholars = Company.query.filter_by(type='Scholarship').all()
    safe     = [c for c in scholars if c.status == 'Active']
    risky    = [c for c in scholars if c.status == 'Blacklisted']
    return render_template('admin/scholarships.html',
                           scholars = scholars,
                           safe     = safe,
                           risky    = risky)


# ============================================================
# ADMIN — LEGAL (PAO)
# ============================================================

@app.route('/admin/legal')
def admin_legal():
    lawyers         = Lawyer.query.all()
    pending_reports = IncidentReport.query.filter_by(status='Pending').all()
    legal_requests  = LegalAidRequest.query.order_by(LegalAidRequest.id.desc()).all()

    print(f"[SENTINEL] /admin/legal → {len(legal_requests)} legal aid request(s) fetched from DB")
    for r in legal_requests:
        print(f"  → ID={r.id} | {r.fullname} | {r.concern_type} | {r.status}")

    return render_template(
        'admin/legal.html',
        lawyers         = lawyers,
        pending_reports = pending_reports,
        legal_requests  = legal_requests
    )


@app.route('/admin/legal/toggle/<int:id>')
def admin_toggle_lawyer(id):
    lawyer              = Lawyer.query.get_or_404(id)
    lawyer.is_available = not lawyer.is_available
    db.session.commit()
    status = "Available" if lawyer.is_available else "Unavailable"
    flash(f"Atty. {lawyer.name} is now {status}.", "info")
    return redirect(url_for('admin_legal'))


@app.route('/admin/legal/assign', methods=['POST'])
def admin_assign_lawyer():
    lawyer_id   = request.form.get('lawyer_id')
    incident_id = request.form.get('incident_id')
    lawyer      = Lawyer.query.get(lawyer_id)
    incident    = IncidentReport.query.get(incident_id)
    if lawyer and incident:
        flash(f"Atty. {lawyer.name} assigned to incident #{incident.id} ({incident.incident_type}).", "success")
    return redirect(url_for('admin_legal'))


@app.route('/admin/legal/resolve/<int:id>')
def admin_resolve_legal_request(id):
    req        = LegalAidRequest.query.get_or_404(id)
    req.status = 'Resolved'
    db.session.commit()
    flash(f"Legal aid request #{id} marked as Resolved.", "success")
    return redirect(url_for('admin_legal'))


@app.route('/admin/legal/archive/<int:id>')
def admin_archive_legal_request(id):
    req        = LegalAidRequest.query.get_or_404(id)
    req.status = 'Archived'
    db.session.commit()
    flash(f"Legal aid request #{id} archived.", "warning")
    return redirect(url_for('admin_legal'))


# ============================================================
# ADMIN — REPORTS (PDF Download)
# ============================================================

@app.route('/admin/reports')
def admin_reports():
    companies = Company.query.all()
    reports   = IncidentReport.query.all()
    return render_template('admin/reports.html', companies=companies, reports=reports)


@app.route('/admin/reports/pdf/<int:id>')
def admin_generate_pdf(id):
    co     = Company.query.get_or_404(id)
    buffer = io.BytesIO()
    p      = canvas.Canvas(buffer)
    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, 800, "PROJECT SENTINEL — COMPLIANCE NOTICE")
    p.setFont("Helvetica", 12)
    p.drawString(100, 770, f"Company: {co.name}")
    p.drawString(100, 755, f"SEC/Permit #: {co.sec_id}")
    p.drawString(100, 740, f"Industry: {co.industry}")
    p.drawString(100, 725, f"Current Status: {co.status}")
    p.drawString(100, 710, f"Compliance Score: {co.compliance_score}/100")
    p.line(100, 700, 500, 700)
    p.drawString(100, 685, "Official record of DOLE/Sentinel agency standing.")
    p.drawString(100, 670, "Generated by Project Sentinel Partner Portal.")
    p.showPage()
    p.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True,
                     download_name=f"Sentinel_Notice_{co.name}.pdf",
                     mimetype='application/pdf')


@app.route('/admin/reports/pdf-all')
def admin_generate_all_pdf():
    companies = Company.query.all()
    buffer    = io.BytesIO()
    p         = canvas.Canvas(buffer)
    y         = 800
    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, y, "PROJECT SENTINEL — FULL COMPANY REGISTRY REPORT")
    y -= 30
    p.setFont("Helvetica", 10)
    for co in companies:
        if y < 100:
            p.showPage()
            y = 800
        p.drawString(100, y, f"{co.name} | {co.sec_id} | {co.status} | Score: {co.compliance_score}/100")
        y -= 18
    p.showPage()
    p.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True,
                     download_name="Sentinel_Full_Report.pdf",
                     mimetype='application/pdf')


# ============================================================
# ADMIN — AGENCY SETTINGS
# ============================================================

_settings = {"system_name": "Project Sentinel", "maintenance_mode": False}


@app.route('/admin/settings', methods=['GET', 'POST'])
def admin_settings():
    global _settings
    if request.method == 'POST':
        _settings['system_name']      = request.form.get('system_name', _settings['system_name'])
        _settings['maintenance_mode'] = True if request.form.get('maintenance_mode') else False
        flash("Settings saved successfully.", "success")
        return redirect(url_for('admin_settings'))
    return render_template('admin/settings.html', settings=_settings)


# ============================================================
# DATABASE SEEDING
# ============================================================

def seed_data():
    if Company.query.count() == 0:
        db.session.add(Company(name="CyberCore Systems",                   sec_id="SEC/O06", industry="Software",        type="Local OJT",  skills_vector="1,0,0,1", compliance_score=98))
        db.session.add(Company(name="Nexus Hardware Solutions",            sec_id="SEC/O07", industry="IT Infra",        type="Local OJT",  skills_vector="0,1,1,0", compliance_score=95))
        db.session.add(Company(name="Vertex Innovation Lab",               sec_id="SEC/O08", industry="Consultancy",     type="Local OJT",  skills_vector="1,1,0,0", compliance_score=97))
        db.session.add(Company(name="Global Accessible Tech (Singapore)",  sec_id="SEC/W08", industry="IT Support",      type="Overseas",   skills_vector="1,1,0,0", compliance_score=99))
        db.session.add(Company(name="EuroCare Inclusion Group (Germany)",  sec_id="SEC/W09", industry="Healthcare Admin",type="Overseas",   skills_vector="0,0,1,0", compliance_score=94))
        db.session.add(Company(name="Pacific Remote Services (Japan)",     sec_id="SEC/W10", industry="Design/CX",      type="Overseas",   skills_vector="0,0,1,1", compliance_score=96))
        db.session.add(Company(name="Global Scholar Fund",                 sec_id="SEC/S01", industry="Education",      type="Scholarship", skills_vector="0,0,0,0", compliance_score=98))
        db.session.add(Company(name="Unsafe Logistics Corp",               sec_id="SEC/B04", industry="Logistics",      type="Local OJT",  skills_vector="0,0,0,0", status="Blacklisted", compliance_score=25))
        db.session.commit()

    if Lawyer.query.count() == 0:
        db.session.add(Lawyer(name="Maria Clara",      specialization="Labor Rights",       is_available=True))
        db.session.add(Lawyer(name="Jose Rizal",       specialization="PWD Advocacy",       is_available=True))
        db.session.add(Lawyer(name="Andres Bonifacio", specialization="Overseas Contracts", is_available=False))
        db.session.commit()

    if LegalAidRequest.query.count() == 0:
        db.session.add(LegalAidRequest(
            fullname         = 'Juan dela Cruz',
            email            = 'juan@email.com',
            contact          = '+63 912 345 6789',
            concern_type     = 'Unpaid Wages / OJT',
            company_involved = 'City Industrial BPO',
            concern          = 'My OJT allowance has not been released for 3 months despite completion of 500 hours.',
            is_anonymous     = False,
            status           = 'Pending'
        ))
        db.session.commit()
        print("[SENTINEL] Database seeded successfully.")


# ============================================================
# MIGRATION — safely add missing columns
# ============================================================

def migrate_db():
    from sqlalchemy import text
    with db.engine.connect() as conn:
        # ── legal_aid_request ──
        result   = conn.execute(text("PRAGMA table_info(legal_aid_request)"))
        existing = {row[1] for row in result.fetchall()}

        migrations = [
            ("concern_type",     "ALTER TABLE legal_aid_request ADD COLUMN concern_type VARCHAR(100) DEFAULT 'Other'"),
            ("company_involved", "ALTER TABLE legal_aid_request ADD COLUMN company_involved VARCHAR(150)"),
            ("is_anonymous",     "ALTER TABLE legal_aid_request ADD COLUMN is_anonymous BOOLEAN DEFAULT 0"),
        ]
        for col_name, sql in migrations:
            if col_name not in existing:
                conn.execute(text(sql))
                print(f"[MIGRATION] Added column: legal_aid_request.{col_name}")

        conn.commit()



"""
=================================================================
  PROJECT SENTINEL — OJT PORTAL ADDITIONS
  Paste these routes into your existing app.py.
  They add: /apply, /report-company, /applications
  They add: OJTApplication model (new table, no conflicts).
=================================================================
"""

# ── ADD THIS MODEL alongside your existing models ─────────────

class OJTApplication(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, default=1)          # replace with session user id when auth is added
    company_name = db.Column(db.String(150), nullable=False)
    timestamp    = db.Column(db.DateTime, default=db.func.now())
    status       = db.Column(db.String(20), default='Pending')  # Pending / Approved / Rejected

# ── ADD THIS MODEL alongside your existing models ─────────────

class CompanyReport(db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    company_name  = db.Column(db.String(150))
    reporter_name = db.Column(db.String(150))
    contact       = db.Column(db.String(100))
    message       = db.Column(db.Text)
    timestamp     = db.Column(db.DateTime, default=db.func.now())
    status        = db.Column(db.String(20), default='Pending')


# ── ROUTE: Apply for OJT Placement ────────────────────────────

@app.route('/apply', methods=['POST'])
def apply_ojt():
    """
    Accepts JSON: { "company_name": "Company Name" }
    Returns  JSON: { "status": "success"|"error", "message": "..." }
    """
    data = request.get_json(silent=True) or {}
    company_name = (data.get('company_name') or '').strip()

    if not company_name:
        return jsonify({'status': 'error', 'message': 'Company name is required.'}), 400

    # Verify company exists and is active
    company = Company.query.filter_by(name=company_name, status='Active').first()
    if not company:
        return jsonify({'status': 'error', 'message': 'Company not found or is not accepting applications.'}), 404

    # Prevent duplicate applications (per session — extend with real user_id when auth is added)
    # For now: check by company_name + status Pending/Approved
    existing = OJTApplication.query.filter_by(
        company_name=company_name,
        status='Pending'
    ).first()
    if existing:
        return jsonify({'status': 'error', 'message': 'You have already applied to this company.'}), 409

    new_app = OJTApplication(
        user_id      = 1,            # TODO: replace with session['user_id'] when auth is ready
        company_name = company_name,
        status       = 'Pending'
    )
    db.session.add(new_app)
    db.session.commit()

    return jsonify({
        'status': 'success',
        'message': f'Application to {company_name} submitted successfully! You will be notified of any updates.',
        'application_id': new_app.id
    }), 201


# ── ROUTE: Report a Company ────────────────────────────────────

@app.route('/report-company', methods=['POST'])
def report_company():
    """
    Accepts JSON: {
        "company_name":  "...",
        "reporter_name": "...",
        "contact":       "...",
        "message":       "..."
    }
    Returns JSON: { "status": "success"|"error", "message": "..." }
    """
    data = request.get_json(silent=True) or {}

    company_name  = (data.get('company_name')  or '').strip()
    reporter_name = (data.get('reporter_name') or '').strip()
    contact       = (data.get('contact')       or '').strip()
    message       = (data.get('message')       or '').strip()

    if not all([company_name, reporter_name, contact, message]):
        return jsonify({'status': 'error', 'message': 'All fields are required.'}), 400

    new_report = CompanyReport(
        company_name  = company_name,
        reporter_name = reporter_name,
        contact       = contact,
        message       = message,
        status        = 'Pending'
    )
    db.session.add(new_report)
    db.session.commit()

    return jsonify({
        'status': 'success',
        'message': 'Report submitted. Sentinel will review it within 3–5 business days.'
    }), 201


# ── ROUTE: My Applications Page ───────────────────────────────

@app.route('/applications')
def my_applications():
    """
    Displays all OJT applications for the current user.
    Returns the applications.html template.
    """
    # TODO: filter by session['user_id'] when auth is added
    apps = OJTApplication.query.filter_by(user_id=1).order_by(OJTApplication.timestamp.desc()).all()
    return render_template('applications.html', applications=apps)


# ── ADMIN ROUTE: View All OJT Applications ────────────────────

@app.route('/admin/applications')
def admin_applications():
    """Admin view — all OJT applications with status management."""
    apps = OJTApplication.query.order_by(OJTApplication.timestamp.desc()).all()
    return render_template('admin/applications.html', applications=apps)


@app.route('/admin/applications/update/<int:app_id>', methods=['POST'])
def admin_update_application(app_id):
    """Update application status: Pending → Approved / Rejected."""
    app_record = OJTApplication.query.get_or_404(app_id)
    new_status = request.form.get('status', 'Pending')
    if new_status in ('Pending', 'Approved', 'Rejected'):
        app_record.status = new_status
        db.session.commit()
        flash(f"Application #{app_id} updated to {new_status}.", "success")
    return redirect(url_for('admin_applications'))


# ── ADMIN ROUTE: View All Company Reports ─────────────────────

@app.route('/admin/company-reports')
def admin_company_reports():
    """Admin view — all company reports filed via the OJT portal."""
    reports = CompanyReport.query.order_by(CompanyReport.timestamp.desc()).all()
    return render_template('admin/company_reports.html', reports=reports)


@app.route('/admin/company-reports/resolve/<int:report_id>')
def admin_resolve_company_report(report_id):
    report = CompanyReport.query.get_or_404(report_id)
    report.status = 'Resolved'
    db.session.commit()
    flash(f"Company report #{report_id} marked as Resolved.", "success")
    return redirect(url_for('admin_company_reports'))


from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3


# ... existing code ...

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Get data from the form
        account_type = request.form.get('account_type')
        first_name = request.form.get('firstname')
        last_name = request.form.get('lastname')
        birthdate = request.form.get('birthdate')
        gender = request.form.get('gender')
        contact = request.form.get('contact')
        address = request.form.get('address')
        pwd_id = request.form.get('pwd_id')
        email = request.form.get('email')
        password = request.form.get('password')  # Use generate_password_hash(password) here

        try:
            conn = sqlite3.connect('instance/sentinel.db')
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO users (
                    account_type, first_name, last_name, birthdate, 
                    gender, contact, address, pwd_id, email, password
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (account_type, first_name, last_name, birthdate,
                  gender, contact, address, pwd_id, email, password))

            conn.commit()
            conn.close()

            # Since your HTML handles the success UI via JS,
            # you can return a JSON success message or redirect.
            return redirect(url_for('login'))

        except sqlite3.IntegrityError:
            flash("Email already registered.")
            return redirect(url_for('register'))
        except Exception as e:
            flash(f"An error occurred: {e}")
            return redirect(url_for('register'))

    return render_template('register.html')


# ============================================================
# APP INITIALIZATION
# ============================================================



if __name__ == '__main__':
    if not os.path.exists('instance'):
        os.makedirs('instance')

    with app.app_context():
        db.create_all()
        migrate_db()
        seed_data()

    app.run(debug=True)
import hashlib, json, os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pypdf import PdfReader
from .db import db, init_db
from .logic import extract_requirements, compare
from .tinyfish import discover

load_dotenv()
BASE = Path(__file__).resolve().parent.parent
FRONT = BASE / "frontend"
UPLOADS = Path(os.getenv("BIDGUARD_UPLOAD_DIR", "uploads"))
UPLOADS.mkdir(parents=True, exist_ok=True)
app = FastAPI(title="BidGuard", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(FRONT)), name="static")

def now(): return datetime.now(timezone.utc).isoformat()
def key_for(title, ref, url): return hashlib.sha256((ref.strip().lower() or url.strip().lower() or title.lower()).encode()).hexdigest()

def save_tender(d, source):
    title, url = str(d.get("title") or "").strip(), str(d.get("source_url") or "").strip()
    p = urlparse(url)
    if not title or p.scheme not in ("http","https") or not p.netloc: return None, False
    ref = str(d.get("tender_reference") or "")
    key = key_for(title, ref, url)
    with db() as c:
        old = c.execute("SELECT id FROM tenders WHERE tender_key=?", (key,)).fetchone()
        if old: return old["id"], False
        cur = c.execute("""INSERT INTO tenders(tender_key,title,tender_reference,authority,location,closing_date,estimated_value,source_url,source_name,retrieved_at,status,raw_text,analysis_json)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""", (key,title[:500],ref[:250],str(d.get("authority") or "")[:500],str(d.get("location") or "")[:250],str(d.get("closing_date") or "")[:250],str(d.get("estimated_value") or "")[:250],url[:2000],source,now(),"discovered",str(d.get("raw_text") or "")[:200000],"{}"))
        return cur.lastrowid, True

@app.on_event("startup")
def startup(): init_db()

@app.get("/")
def index(): return FileResponse(FRONT / "index.html")

@app.get("/api/health")
def health(): return {"status":"ok","app":"BidGuard","time":now()}

@app.get("/api/company")
def get_company():
    with db() as c: row = c.execute("SELECT data,updated_at FROM company WHERE id=1").fetchone()
    return {"profile":json.loads(row["data"]) if row else {}, "updated_at":row["updated_at"] if row else None}

class Company(BaseModel):
    company_name: str = ""; industry: str = ""; products_services: str = ""; location: str = ""
    operating_regions: str = ""; registration_type: str = ""; years_experience: float | None = None
    annual_turnover: float | None = None; turnover_currency: str = "INR"; turnover_financial_year: str = ""
    certifications: str = ""; completed_projects: str = ""; government_experience: str = ""
    supporting_documents: str = ""; preferred_value_min: float | None = None; preferred_value_max: float | None = None
    preferred_categories: str = ""; preferred_locations: str = ""; keywords: str = ""; exclusions: str = ""

@app.put("/api/company")
def put_company(profile: Company):
    payload = profile.model_dump()
    with db() as c:
        c.execute("INSERT INTO company(id,data,updated_at) VALUES(1,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data,updated_at=excluded.updated_at", (json.dumps(payload),now()))
    return {"status":"saved","profile":payload}

class ManualTender(BaseModel):
    title: str = Field(min_length=3,max_length=500); source_url: str = Field(min_length=8,max_length=2000)
    tender_reference: str = ""; authority: str = ""; location: str = ""; closing_date: str = ""; estimated_value: str = ""; raw_text: str = ""

@app.get("/api/tenders")
def list_tenders(q: str = "", status: str = ""):
    with db() as c: rows = c.execute("SELECT * FROM tenders ORDER BY retrieved_at DESC").fetchall()
    out=[]
    for row in rows:
        d=dict(row)
        if q and q.lower() not in (d["title"]+" "+d["authority"]+" "+d["location"]).lower(): continue
        if status and status!="all" and d["status"]!=status: continue
        d["analysis"]=json.loads(d.pop("analysis_json") or "{}"); out.append(d)
    return {"tenders":out,"count":len(out)}

@app.get("/api/tenders/{tid}")
def tender_detail(tid: int):
    with db() as c:
        row=c.execute("SELECT * FROM tenders WHERE id=?",(tid,)).fetchone()
        docs=c.execute("SELECT id,filename,page_count,uploaded_at FROM documents WHERE tender_id=? ORDER BY id DESC",(tid,)).fetchall()
    if not row: raise HTTPException(404,"Tender not found")
    d=dict(row); d["analysis"]=json.loads(d.pop("analysis_json") or "{}"); d["documents"]=[dict(x) for x in docs]; return d

@app.post("/api/discovery/run")
def run_discovery():
    result=discover(); imported=duplicates=0
    for t in result.get("tenders",[]):
        _,created=save_tender(t,"TinyFish / CPPP")
        imported += int(created); duplicates += int(not created)
    return {"status":result.get("status","error"),"message":result.get("message",""),"imported":imported,"duplicates":duplicates}

@app.post("/api/tenders/manual")
def add_manual(t: ManualTender):
    d=t.model_dump()
    if not d["source_url"].startswith(("https://","http://")): raise HTTPException(400,"Enter an http or https source URL.")
    tid,created=save_tender(d,"Manual entry")
    if tid is None: raise HTTPException(400,"Tender title and valid source URL are required.")
    if not created: return {"status":"duplicate","id":tid,"message":"Tender already exists."}
    return {"status":"created","id":tid}

@app.post("/api/tenders/{tid}/documents")
async def upload_pdf(tid: int, file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"): raise HTTPException(400,"Only PDF files are supported.")
    data=await file.read()
    if len(data)>15*1024*1024: raise HTTPException(413,"PDF exceeds 15 MB.")
    if not data.startswith(b"%PDF"): raise HTTPException(400,"File does not look like a PDF.")
    with db() as c: exists=c.execute("SELECT id FROM tenders WHERE id=?",(tid,)).fetchone()
    if not exists: raise HTTPException(404,"Tender not found.")
    name=Path(file.filename).name.replace(" ","_")[:120]
    path=UPLOADS / f"tender_{tid}_{int(datetime.now().timestamp())}_{name}"; path.write_bytes(data)
    try:
        reader=PdfReader(str(path)); parts=[]
        for i,page in enumerate(reader.pages):
            txt=page.extract_text() or ""
            if txt.strip(): parts.append(f"[Page {i+1}]\\n{txt}")
        extracted="\\n\\n".join(parts); pages=len(reader.pages)
    except Exception as e:
        path.unlink(missing_ok=True); raise HTTPException(400,f"Could not read PDF: {str(e)[:250]}")
    with db() as c:
        c.execute("INSERT INTO documents(tender_id,filename,stored_path,page_count,uploaded_at) VALUES(?,?,?,?,?)",(tid,name,str(path),pages,now()))
        if extracted: c.execute("UPDATE tenders SET raw_text=CASE WHEN raw_text='' THEN ? ELSE raw_text || char(10) || ? END WHERE id=?",(extracted[:200000],extracted[:200000],tid))
    return {"status":"uploaded","filename":name,"page_count":pages,"characters_extracted":len(extracted),"ocr_required":not bool(extracted.strip()),"message":"Text extracted." if extracted.strip() else "This may be a scanned PDF; OCR is not included."}

@app.post("/api/tenders/{tid}/analyze")
def analyze(tid: int):
    with db() as c:
        tender=c.execute("SELECT * FROM tenders WHERE id=?",(tid,)).fetchone()
        comp=c.execute("SELECT data FROM company WHERE id=1").fetchone()
    if not tender: raise HTTPException(404,"Tender not found.")
    company=json.loads(comp["data"]) if comp else {}
    requirements=extract_requirements(tender["raw_text"] or "")
    findings=compare(requirements,company)
    result={"generated_at":now(),"status":"preliminary","requirements_found":len(requirements),"findings":findings,
      "limitations":["This is preliminary decision support, not an official eligibility determination.","Heuristic extraction may miss clauses, exceptions, amendments, tables and scanned content.","Page markers may be present in extracted text, but exact clause/page citations require human verification.","Verify all important findings against the original tender documents."],
      "next_actions":["Verify the latest tender notice and all corrigenda on the official source.","Review every Potential mismatch, Missing evidence and Needs manual verification finding.","Confirm turnover period, financial year, experience type, exemptions, EMD and required forms.","Have an authorized person verify the final bid decision."]}
    with db() as c: c.execute("UPDATE tenders SET analysis_json=?,status='analyzed' WHERE id=?",(json.dumps(result),tid))
    return result

@app.delete("/api/tenders/{tid}")
def delete_tender(tid: int):
    with db() as c:
        docs=c.execute("SELECT stored_path FROM documents WHERE tender_id=?",(tid,)).fetchall()
        if not c.execute("SELECT id FROM tenders WHERE id=?",(tid,)).fetchone(): raise HTTPException(404,"Tender not found.")
        c.execute("DELETE FROM documents WHERE tender_id=?",(tid,)); c.execute("DELETE FROM tenders WHERE id=?",(tid,))
    for d in docs:
        try: Path(d["stored_path"]).unlink(missing_ok=True)
        except OSError: pass
    return {"status":"deleted"}

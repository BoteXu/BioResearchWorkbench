"""Unmodified searches and open-access source retrieval without a second model."""
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote, urljoin, urlsplit
from http_client import get_json, request

HERE = Path(__file__).resolve().parent
EP = "https://www.ebi.ac.uk/europepmc/webservices/rest"


def _count(value):
    if type(value) is not int or not 1 <= value <= 100:
        raise ValueError("max_results must be an integer from 1 to 100")


def ncbi_search(database, query, max_results=10):
    _count(max_results)
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Provide a nonempty query")
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    search = get_json(base + "esearch.fcgi", {"db": database, "term": query, "retmax": max_results, "retmode": "json", "tool": "CodexBiomniDirect"})
    if search.get("error") or search.get("esearchresult", {}).get("ERROR"):
        return {"success": False, "query": query, "search": search}
    ids = search.get("esearchresult", {}).get("idlist", [])
    result = {"success": True, "database": database, "query": query, "query_translation": search.get("esearchresult", {}).get("querytranslation"), "total_count": search.get("esearchresult", {}).get("count"), "ids": ids, "search": search}
    if not ids:
        result["records"] = []
        return result
    if database == "pubmed":
        raw, _ = request(base + "efetch.fcgi", params={"db": database, "id": ",".join(ids), "retmode": "xml", "tool": "CodexBiomniDirect"})
        root = ET.fromstring(raw)
        records = []
        for article in root.findall(".//PubmedArticle"):
            title = article.find(".//ArticleTitle")
            abstract = article.findall(".//AbstractText")
            records.append({"pmid": article.findtext(".//PMID"), "title": "".join(title.itertext()) if title is not None else None, "abstract": [{"label": a.get("Label"), "text": "".join(a.itertext())} for a in abstract], "journal": article.findtext(".//Journal/Title"), "identifiers": {a.get("IdType"): a.text for a in article.findall(".//ArticleId")}})
        result["records"] = records
        result["xml"] = raw.decode("utf8")
    else:
        result["records"] = get_json(base + "esummary.fcgi", {"db": database, "id": ",".join(ids), "retmode": "json", "tool": "CodexBiomniDirect"})
    return result


def query_pubmed(query: str, max_papers: int = 10, max_retries: int = 0) -> dict:
    """Search PubMed, preserving the submitted query. max_retries is compatibility-only."""
    return ncbi_search("pubmed", query, max_papers)


def query_europepmc(query: str, max_results: int = 10, cursor: str = "*") -> dict:
    """Search Europe PMC core metadata; return cursor and the exact query."""
    _count(max_results)
    result = get_json(EP + "/search", {"query": query, "format": "json", "resultType": "core", "pageSize": max_results, "cursorMark": cursor})
    return {"success": "errCode" not in result, "query": query, "result": result}


def doi_metadata(doi: str) -> dict:
    """Retrieve Crossref DOI metadata, including corrections/updates where deposited."""
    doi = doi.removeprefix("https://doi.org/").strip()
    if not re.fullmatch(r"10\.\d{4,9}/\S+", doi):
        raise ValueError("Invalid DOI")
    result = get_json("https://api.crossref.org/works/" + quote(doi, safe=""))
    return {"success": True, "doi": doi, "result": result}


def fetch_open_access_article(pmcid: str, include_supplements: bool = False) -> dict:
    """Retrieve Europe PMC OA JATS XML and optionally the supplementary ZIP."""
    pmcid = pmcid.upper()
    if not re.fullmatch(r"PMC\d+", pmcid):
        raise ValueError("Provide a PMCID such as PMC4255742")
    raw, source = request(EP + f"/{pmcid}/fullTextXML")
    root = ET.fromstring(raw)
    if root.tag != "article":
        raise ValueError("The endpoint did not return an open-access JATS article")
    folder = HERE / "articles" / pmcid
    folder.mkdir(parents=True, exist_ok=True)
    xml_path = folder / "fulltext.xml"
    xml_path.write_bytes(raw)
    sections = []
    for section in root.findall(".//body//sec"):
        title = section.find("title")
        paragraphs = section.findall("p")
        sections.append({"id": section.get("id"), "title": "".join(title.itertext()) if title is not None else "", "paragraphs": ["".join(p.itertext()) for p in paragraphs]})
    supplements = []
    for node in root.findall(".//supplementary-material"):
        supplements.append({"id": node.get("id"), "description": " ".join(node.itertext()), "links": [e.get("{http://www.w3.org/1999/xlink}href") for e in node.iter() if e.get("{http://www.w3.org/1999/xlink}href")]})
    result = {"success": True, "pmcid": pmcid, "xml_file": str(xml_path), "xml_sha256": hashlib.sha256(raw).hexdigest(), "license_text": [" ".join(n.itertext()) for n in root.findall(".//permissions")], "sections": sections, "supplementary_material": supplements, "supplement_download": {"state": "not_requested"}}
    if include_supplements:
        try:
            data, supp_source = request(EP + f"/{pmcid}/supplementaryFiles", limit_bytes=100_000_000)
            if not data.startswith(b"PK"):
                raise ValueError("Supplement endpoint returned no ZIP archive")
            path = folder / "supplements.zip"
            path.write_bytes(data)
            result["supplement_download"] = {"state": "downloaded", "file": str(path), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
        except Exception as exc:
            result["supplement_download"] = {"state": "unavailable", "error": str(exc)}
    return result


def fetch_supplementary_info_from_doi(doi: str, output_dir: str = "supplementary_info") -> dict:
    """Resolve DOI through Europe PMC, then retrieve available OA supplements."""
    # Compatibility argument retained; files have a stable managed directory.
    doi = doi.removeprefix("https://doi.org/").strip()
    if not re.fullmatch(r"10\.\d{4,9}/\S+", doi) or '"' in doi:
        raise ValueError("Invalid DOI")
    metadata = query_europepmc(f'DOI:"{doi}"', 5)
    records = metadata["result"].get("resultList", {}).get("result", [])
    eligible = next((r for r in records if r.get("pmcid") and r.get("isOpenAccess") == "Y"), None)
    if not eligible:
        return {"success": True, "retrieval_state": "no_open_access_match", "doi": doi, "metadata": metadata, "files": [], "publisher_discovery": discover_publisher_supplements(doi)}
    article = fetch_open_access_article(eligible["pmcid"], True)
    article["doi"] = doi
    if article["supplement_download"]["state"] != "downloaded":
        article["publisher_discovery"] = discover_publisher_supplements(doi)
    return article


def discover_publisher_supplements(doi: str, max_links: int = 30) -> dict:
    """Discover public publisher links; report blocked pages and never infer absent files."""
    from bs4 import BeautifulSoup
    _count(max_links)
    metadata = doi_metadata(doi)
    doi = metadata["doi"]
    try:
        raw, source = request("https://doi.org/" + quote(doi, safe="/"))
        page_url = source["url"]
        soup = BeautifulSoup(raw, "html.parser")
        candidates = []
        seen = set()
        for node in soup.find_all("a", href=True):
            label = node.get_text(" ", strip=True)
            href = node["href"]
            text = (label + " " + href).lower()
            if not any(term in text for term in ("supplement", "moesm", "supporting information", "additional file", "appendix")):
                continue
            url = urljoin(page_url, href)
            if urlsplit(url).scheme != "https" or url in seen:
                continue
            seen.add(url)
            candidates.append({"url": url, "label": label, "file_extension": Path(urlsplit(url).path).suffix.lower(), "state": "discovered_not_downloaded"})
        return {"success": True, "doi": doi, "publisher_page": page_url, "candidates": candidates[:max_links], "total_candidates": len(candidates), "limitations": ["Links may lead to HTML pages or unavailable files. Discovery does not prove file accessibility."]}
    except Exception as exc:
        return {"success": False, "doi": doi, "error": str(exc), "candidates": [], "metadata": metadata}


def download_publisher_supplement(discovery_receipt: str, url: str) -> dict:
    """Download a URL explicitly listed in an intact prior discovery receipt."""
    import uuid
    receipt_path = Path(discovery_receipt).resolve(strict=True)
    if receipt_path.parent != (HERE / "results").resolve() or not receipt_path.name.endswith(".receipt.json"):
        raise ValueError("Provide a bridge discovery receipt file")
    receipt = json.loads(receipt_path.read_text(encoding="utf8"))
    if receipt["tool"] not in {"biomni.tool.literature.discover_publisher_supplements", "biomni.tool.literature.fetch_supplementary_info_from_doi"}:
        raise ValueError("Receipt must be from supplement discovery")
    result_path = Path(receipt["result_file"]).resolve()
    if result_path.parent != (HERE / "results").resolve():
        raise ValueError("Unexpected discovery file location")
    raw = result_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != receipt["sha256"]:
        raise ValueError("Discovery receipt hash mismatch")
    discovery = json.loads(raw)
    candidates = discovery.get("candidates", discovery.get("publisher_discovery", {}).get("candidates", []))
    if url not in {item["url"] for item in candidates}:
        raise ValueError("URL was not listed in this discovery receipt")
    data, source = request(url, limit_bytes=100_000_000)
    if "text/html" in (source["content_type"] or "").lower():
        return {"success": False, "error": "The discovered link returned an HTML page, not a supplementary file", "url": source["url"]}
    folder = HERE / "supplements" / uuid.uuid4().hex
    folder.mkdir(parents=True)
    suffix = Path(urlsplit(source["url"]).path).suffix.lower()
    suffix = suffix if re.fullmatch(r"\.[a-z0-9]{1,8}", suffix) else ".bin"
    path = folder / ("supplement" + suffix)
    path.write_bytes(data)
    return {"success": True, "url": source["url"], "file": str(path), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "content_type": source["content_type"]}


def extract_local_document(path: str) -> dict:
    """Extract text from local PDF, DOCX, XML/JATS or UTF-8 text without uploading it."""
    p = Path(path).resolve(strict=True)
    suffix = p.suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(p)
        pages = [{"page": i + 1, "text": page.extract_text() or ""} for i, page in enumerate(reader.pages)]
        return {"success": True, "path": str(p), "pages": pages, "ocr_required": any(not page["text"].strip() for page in pages)}
    if suffix == ".docx":
        import zipfile
        with zipfile.ZipFile(p) as archive:
            xml = archive.read("word/document.xml")
        root = ET.fromstring(xml)
        text = "\n".join("".join(n.itertext()) for n in root.findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"))
    elif suffix in {".xml", ".jats"}:
        text = " ".join(ET.parse(p).getroot().itertext())
    elif suffix in {".txt", ".md", ".csv", ".tsv"}:
        text = p.read_text(encoding="utf8")
    else:
        raise ValueError("Supported documents: PDF, DOCX, XML/JATS, TXT, MD, CSV, TSV")
    return {"success": True, "path": str(p), "text": text}

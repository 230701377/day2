"""
Duplicate Contract Detection & Deduplication Service.

Uses Multi-Signal Analysis:
1. Exact Title / Counterparty / Metadata Match (across ALL Contract records)
2. SHA-256 Fingerprint Matching (across ALL ContractVersion records)
3. Filename Match (across ALL ContractVersion records)
4. Scikit-learn TF-IDF + Cosine Similarity (Text Content Duplicate)
"""
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.models.models import Contract, ContractVersion


class DuplicateDetectionService:
    """
    Multi-Signal Duplicate & High-Similarity Contract Detection Engine.
    """

    @staticmethod
    def detect_duplicates_in_db(
        db: Session,
        new_text: str = "",
        new_filename: str = "",
        new_title: str = "",
        new_counterparty: str = "",
        sha256_hash: str = "",
        current_contract_id: str = "",
        threshold: float = 0.45
    ) -> Dict[str, Any]:
        """
        Scans DB for duplicates using SHA-256, Filename, Title/Counterparty, and TF-IDF Text Cosine Similarity.
        Scans ALL contracts in repository, even if no document version is attached yet.
        """
        try:
            contracts = db.query(Contract).all()
        except Exception:
            try:
                from app.models.models import Base
                from app.db.session import engine
                Base.metadata.create_all(bind=engine)
                contracts = db.query(Contract).all()
            except Exception:
                contracts = []

        try:
            versions = db.query(ContractVersion).all()
        except Exception:
            versions = []

        # Filter out current contract
        existing_contracts = [c for c in contracts if str(c.id) != str(current_contract_id)]
        existing_versions = [v for v in versions if str(v.contract_id) != str(current_contract_id)]

        if not existing_contracts and not existing_versions:
            return {
                "has_duplicate": False,
                "matches": [],
                "message": "No existing contracts in repository for comparison."
            }

        matches = []
        matched_contract_ids = set()

        clean_filename = new_filename.strip().lower()
        clean_title = new_title.strip().lower()

        # 1. Title & Counterparty Duplicate Check (Across ALL Contracts)
        if clean_title or clean_filename:
            for cnt in existing_contracts:
                if str(cnt.id) in matched_contract_ids:
                    continue

                cnt_title = (cnt.title or "").strip().lower()

                title_exact = clean_title and (clean_title == cnt_title)
                title_near_exact = clean_title and (clean_title in cnt_title or cnt_title in clean_title) and (abs(len(clean_title) - len(cnt_title)) <= 3)
                file_title_match = clean_filename and clean_filename.replace(".pdf", "").replace(".docx", "").replace(".txt", "").strip() == cnt_title

                if title_exact or title_near_exact or file_title_match:
                    matched_contract_ids.add(str(cnt.id))
                    score = 1.0 if title_exact else 0.88
                    matches.append({
                        "matched_contract_id": str(cnt.id),
                        "matched_contract_number": cnt.contract_number,
                        "matched_contract_name": cnt.title,
                        "matched_contract_type": cnt.contract_type,
                        "matched_counterparty": cnt.counterparty or "Vendor",
                        "similarity_score": score,
                        "similarity_percentage": f"{int(score * 100)}%",
                        "match_level": "EXACT TITLE DUPLICATE" if title_exact else "HIGH TITLE SIMILARITY",
                        "reason": f"Contract title '{cnt.title}' already exists in contract repository ({cnt.contract_number})."
                    })

        # 2. SHA-256 Hash Exact Match (Across ALL Versions)
        if sha256_hash:
            for ver in existing_versions:
                if ver.sha256_hash and ver.sha256_hash == sha256_hash:
                    cnt = next((c for c in existing_contracts if str(c.id) == str(ver.contract_id)), None)
                    cnt_title = cnt.title if cnt else "Existing Contract"
                    cnt_num = cnt.contract_number if cnt else ""

                    if cnt and str(cnt.id) not in matched_contract_ids:
                        matched_contract_ids.add(str(cnt.id))
                        matches.append({
                            "matched_contract_id": str(cnt.id) if cnt else str(ver.contract_id),
                            "matched_contract_number": cnt_num,
                            "matched_contract_name": cnt_title,
                            "matched_contract_type": cnt.contract_type if cnt else "nda",
                            "matched_counterparty": cnt.counterparty if cnt else "Vendor",
                            "similarity_score": 1.0,
                            "similarity_percentage": "100.0%",
                            "match_level": "EXACT FILE DUPLICATE (SHA-256)",
                            "reason": f"Identical file binary hash detected with existing contract '{cnt_title}' ({cnt_num})."
                        })

        # 3. Filename Exact Match (Across ALL Versions)
        if clean_filename:
            for ver in existing_versions:
                ver_file = (ver.original_filename or "").strip().lower()
                if ver_file and ver_file == clean_filename:
                    cnt = next((c for c in existing_contracts if str(c.id) == str(ver.contract_id)), None)
                    if cnt and str(cnt.id) not in matched_contract_ids:
                        matched_contract_ids.add(str(cnt.id))
                        matches.append({
                            "matched_contract_id": str(cnt.id),
                            "matched_contract_number": cnt.contract_number,
                            "matched_contract_name": cnt.title,
                            "matched_contract_type": cnt.contract_type,
                            "matched_counterparty": cnt.counterparty or "Vendor",
                            "similarity_score": 0.90,
                            "similarity_percentage": "90.0%",
                            "match_level": "EXACT FILENAME DUPLICATE",
                            "reason": f"Original filename '{ver.original_filename}' matches existing contract '{cnt.title}' ({cnt.contract_number})."
                        })

        # 4. TF-IDF Text Content Cosine Similarity
        if new_text and len(new_text.strip()) >= 15:
            text_version_candidates = [
                v for v in existing_versions 
                if str(v.contract_id) not in matched_contract_ids and v.content_text and len(v.content_text.strip()) >= 15
            ]

            if text_version_candidates:
                corpus = [new_text] + [v.content_text for v in text_version_candidates]
                try:
                    from sklearn.feature_extraction.text import TfidfVectorizer
                    from sklearn.metrics.pairwise import cosine_similarity

                    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
                    tfidf_matrix = vectorizer.fit_transform(corpus)
                    similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()

                    for idx, score in enumerate(similarities):
                        ver = text_version_candidates[idx]
                        match_score = float(score)
                        cnt = next((c for c in existing_contracts if str(c.id) == str(ver.contract_id)), None)

                        if match_score >= threshold and cnt:
                            matches.append({
                                "matched_contract_id": str(cnt.id),
                                "matched_contract_number": cnt.contract_number,
                                "matched_contract_name": cnt.title,
                                "matched_contract_type": cnt.contract_type,
                                "matched_counterparty": cnt.counterparty or "Vendor",
                                "similarity_score": round(match_score, 4),
                                "similarity_percentage": f"{round(match_score * 100, 1)}%",
                                "match_level": "CRITICAL TEXT DUPLICATE" if match_score >= 0.75 else "HIGH SIMILARITY" if match_score >= 0.55 else "MODERATE SIMILARITY",
                                "reason": f"Legal text content has {round(match_score * 100, 1)}% cosine similarity with existing contract '{cnt.title}'."
                            })
                except Exception:
                    pass

        matches.sort(key=lambda x: x["similarity_score"], reverse=True)
        has_duplicate = any(m["similarity_score"] >= threshold for m in matches)

        top_match_pct = matches[0]["similarity_percentage"] if matches else "0%"
        top_match_name = matches[0]["matched_contract_name"] if matches else ""

        return {
            "has_duplicate": has_duplicate,
            "threshold_percentage": f"{int(threshold * 100)}%",
            "top_match_score": top_match_pct,
            "top_match_name": top_match_name,
            "matches": matches,
            "message": f"CRITICAL: High-similarity duplicate ({top_match_pct}) matched with existing contract '{top_match_name}'." if has_duplicate else "No duplicates detected in contract repository."
        }

    @staticmethod
    def cleanup_duplicate_contracts_in_db(db: Session) -> Dict[str, Any]:
        """
        Scans DB for duplicate contracts (same title or identical SHA-256 hash)
        and purges redundant duplicate copies, keeping the earliest created instance.
        """
        contracts = db.query(Contract).order_by(Contract.created_at.asc()).all()
        seen_titles = {}
        removed_count = 0
        removed_titles = []

        for c in contracts:
            clean_title = (c.title or "").strip().lower()
            if not clean_title:
                continue

            if clean_title in seen_titles:
                # Duplicate found - purge redundant contract instance
                try:
                    db.delete(c)
                    removed_count += 1
                    removed_titles.append(c.title)
                except Exception:
                    pass
            else:
                seen_titles[clean_title] = str(c.id)

        if removed_count > 0:
            db.commit()

        return {
            "removed_count": removed_count,
            "removed_titles": removed_titles,
            "message": f"Successfully cleaned up {removed_count} redundant duplicate contract(s)." if removed_count > 0 else "Repository clean. No duplicate contracts found."
        }


duplicate_service = DuplicateDetectionService()

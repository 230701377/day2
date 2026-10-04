"""Quick fix: delete existing contracts/obligations/clauses/risks so the seed
can re-create them with INR values."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal, engine
from app.models.models import (
    Contract, ContractVersion, Clause, RiskFinding, ContractMetadata,
    Obligation, ApprovalWorkflow, Approval,
)


def main():
    db = SessionLocal()
    try:
        # Delete in dependency order
        db.query(Approval).delete()
        # Don't delete ApprovalWorkflow - they're shared
        db.query(Obligation).delete()
        db.query(RiskFinding).delete()
        db.query(Clause).delete()
        db.query(ContractMetadata).delete()
        db.query(ContractVersion).delete()
        # Re-parent any amendments to NULL before deleting parents
        db.query(Contract).filter(Contract.parent_contract_id.isnot(None)).update(
            {Contract.parent_contract_id: None}, synchronize_session=False
        )
        db.query(Contract).delete()
        db.commit()
        print("Cleared contracts, clauses, risks, obligations, approvals.")
        print("Now run: python scripts/seed.py")
    finally:
        db.close()


if __name__ == "__main__":
    main()

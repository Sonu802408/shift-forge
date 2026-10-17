import json
from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.models.report import MedicalReport, ReportFinding, ReportSummary, ReportStatus
from app.schemas.report import (
    MedicalReportResponse,
    ReportExplanationResponse,
    ReportFindingSchema,
)
from app.core.dependencies import get_current_user
from app.services.file_service import file_service
from app.services.document_processor import document_processor
from app.services.ai_service import ai_service

router = APIRouter(prefix="/reports", tags=["CareBridge AI — Medical Reports"])


@router.post("", response_model=MedicalReportResponse, status_code=status.HTTP_201_CREATED)
@router.post("/upload", response_model=MedicalReportResponse, status_code=status.HTTP_201_CREATED)
def upload_report(
    file: UploadFile = File(...),
    title: str = Form("Medical Laboratory Report"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Uploads and validates a medical report (PDF or Image).
    Extracts readable text via PyMuPDF/OCR.
    """
    unique_filename, file_path, file_size = file_service.save_file(file)

    extracted_text = document_processor.process_document(
        file_path=file_path,
        mime_type=file.content_type or "application/octet-stream",
    )

    report = MedicalReport(
        user_id=current_user.id,
        title=title,
        file_path=file_path,
        original_filename=file.filename or unique_filename,
        mime_type=file.content_type or "application/octet-stream",
        file_size_bytes=file_size,
        extracted_text=extracted_text,
        processing_status=ReportStatus.PENDING,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    return report


@router.get("", response_model=List[MedicalReportResponse])
def list_reports(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lists all medical reports belonging to the authenticated user."""
    if current_user.role in [UserRole.DOCTOR, UserRole.ADMIN]:
        return db.query(MedicalReport).order_by(MedicalReport.created_at.desc()).all()
    return (
        db.query(MedicalReport)
        .filter(MedicalReport.user_id == current_user.id)
        .order_by(MedicalReport.created_at.desc())
        .all()
    )


@router.get("/{report_id}", response_model=MedicalReportResponse)
def get_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieves an authorized medical report by ID."""
    report = db.query(MedicalReport).filter(MedicalReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    if report.user_id != current_user.id and current_user.role not in [UserRole.DOCTOR, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to access this medical report.",
        )
    return report


@router.post("/{report_id}/explain", response_model=ReportExplanationResponse)
def explain_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    CareBridge AI Centerpiece Feature:
    Extracts lab findings, reference ranges, plain-language explanation,
    and tailored questions for doctor consultation.
    """
    report = db.query(MedicalReport).filter(MedicalReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    if report.user_id != current_user.id and current_user.role not in [UserRole.DOCTOR, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to explain this report.",
        )

    # Run AI Explanation
    content_to_analyze = report.extracted_text or f"Medical report: {report.title}"
    analysis = ai_service.explain_medical_report(content_to_analyze, title=report.title)

    # Clean existing findings & summary if re-explaining
    db.query(ReportFinding).filter(ReportFinding.report_id == report.id).delete()
    db.query(ReportSummary).filter(ReportSummary.report_id == report.id).delete()

    # Save extracted findings
    created_findings = []
    for f in analysis.get("findings", []):
        finding_obj = ReportFinding(
            report_id=report.id,
            test_name=f.get("test_name", "Clinical Marker"),
            value=str(f.get("value", "N/A")),
            unit=f.get("unit"),
            reference_range=f.get("reference_range"),
            is_abnormal=bool(f.get("is_abnormal", False)),
            clinical_note=f.get("clinical_note"),
        )
        db.add(finding_obj)
        created_findings.append(finding_obj)

    # Save summary
    summary_obj = ReportSummary(
        report_id=report.id,
        summary=analysis.get("summary", "Report analyzed by CareBridge AI."),
        plain_language_explanation=analysis.get("plain_language_explanation", "Analysis completed."),
        doctor_questions=json.dumps(analysis.get("doctor_questions", [])),
    )
    db.add(summary_obj)

    report.processing_status = ReportStatus.EXPLAINED
    db.commit()
    db.refresh(report)

    return ReportExplanationResponse(
        report_id=report.id,
        title=report.title,
        status=report.processing_status,
        summary=summary_obj.summary,
        plain_language_explanation=summary_obj.plain_language_explanation,
        findings=[ReportFindingSchema.model_validate(f) for f in created_findings],
        doctor_questions=analysis.get("doctor_questions", []),
    )


@router.get("/{report_id}/summary", response_model=ReportExplanationResponse)
@router.get("/{report_id}/analysis", response_model=ReportExplanationResponse)
def get_report_summary(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieves the pre-generated CareBridge AI explanation for a medical report."""
    report = db.query(MedicalReport).filter(MedicalReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    if report.user_id != current_user.id and current_user.role not in [UserRole.DOCTOR, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to view this summary.",
        )

    if not report.summary_rel:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This report has not been explained yet. Call POST /api/v1/reports/{id}/explain first.",
        )

    try:
        questions = json.loads(report.summary_rel.doctor_questions)
    except Exception:
        questions = []

    return ReportExplanationResponse(
        report_id=report.id,
        title=report.title,
        status=report.processing_status,
        summary=report.summary_rel.summary,
        plain_language_explanation=report.summary_rel.plain_language_explanation,
        findings=[ReportFindingSchema.model_validate(f) for f in report.findings],
        doctor_questions=questions,
    )

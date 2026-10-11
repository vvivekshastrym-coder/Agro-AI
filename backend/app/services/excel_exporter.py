"""Agro AI Farmers Registry Excel Exporter
Generates styled Microsoft Excel (.xlsx) workbooks and CSV files containing
comprehensive data of all registered farmers, farms, crops, subscriptions, and diagnosis counts.
"""
import os
import io
import csv
import datetime
from typing import List, Dict, Any
from sqlalchemy.orm import Session
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from ..database.models import User, UserRole, Farm, FarmCrop, UserSubscription, SubscriptionPlanVersion, DiagnosisReport, PaymentOrder

EXPORT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "exports"))


def fetch_farmer_export_data(db: Session) -> List[Dict[str, Any]]:
    """Gathers all registered farmers and joins their agricultural and subscription data."""
    farmers = db.query(User).filter(User.role == UserRole.farmer).order_by(User.created_at.desc()).all()
    # If no farmers with role farmer yet, fall back to all non-admin users
    if not farmers:
        farmers = db.query(User).order_by(User.created_at.desc()).all()

    rows = []
    for u in farmers:
        # Farm info
        farm = db.query(Farm).filter(Farm.user_id == u.id).first()
        
        # Crops
        crop_names = []
        if farm:
            crops = db.query(FarmCrop).filter(FarmCrop.farm_id == farm.id).all()
            crop_names = [c.crop_name for c in crops if c.crop_name]

        # Active subscription
        sub = db.query(UserSubscription).filter(UserSubscription.user_id == u.id).order_by(UserSubscription.created_at.desc()).first()
        sub_plan_name = "None (Free)"
        sub_status = "None"
        sub_end = "—"
        if sub:
            sub_status = sub.status
            sub_end = sub.current_period_end.strftime("%Y-%m-%d") if sub.current_period_end else "—"
            ver = db.query(SubscriptionPlanVersion).filter(SubscriptionPlanVersion.id == sub.plan_version_id).first()
            if ver:
                sub_plan_name = f"{ver.name} (v{ver.version})"

        # Diagnoses count
        diag_count = db.query(DiagnosisReport).filter(DiagnosisReport.farmer_id == u.id).count()

        # Orders count
        orders_count = db.query(PaymentOrder).filter(PaymentOrder.user_id == u.id).count()

        rows.append({
            "id": u.id,
            "full_name": u.full_name or "Not Specified",
            "phone": u.phone or "—",
            "email": u.email or "—",
            "preferred_language": (u.preferred_language or "en").upper(),
            "is_active": "Active" if u.is_active else "Suspended",
            "is_verified": "Verified" if u.is_verified else "Pending",
            "registered_at": u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else "—",
            
            # Farm details
            "state": farm.state if farm and farm.state else "—",
            "district": farm.district if farm and farm.district else "—",
            "pincode": farm.pincode if farm and farm.pincode else "—",
            "total_acres": farm.total_acres if farm and farm.total_acres is not None else 0.0,
            "owned_acres": farm.owned_acres if farm and farm.owned_acres is not None else 0.0,
            "leased_acres": farm.leased_acres if farm and farm.leased_acres is not None else 0.0,
            "soil_type": farm.soil_type if farm and farm.soil_type else "—",
            "irrigation_method": farm.irrigation_method if farm and farm.irrigation_method else "—",
            "water_source": farm.water_source if farm and farm.water_source else "—",
            "crops": ", ".join(crop_names) if crop_names else "None listed",
            
            # Subscriptions & metrics
            "subscription_plan": sub_plan_name,
            "subscription_status": sub_status.capitalize(),
            "subscription_valid_until": sub_end,
            "diagnoses_count": diag_count,
            "orders_count": orders_count,
        })

    return rows


def generate_farmers_excel_bytes(data: List[Dict[str, Any]]) -> bytes:
    """Creates a beautifully styled openpyxl Workbook in memory and returns raw bytes."""
    wb = openpyxl.Workbook()
    
    # Palette constants
    forest_green = "1B4332"
    sage_green = "2D6A4F"
    light_sage = "E8F5E9"
    border_gray = "D1D5DB"
    
    header_fill = PatternFill(start_color=forest_green, end_color=forest_green, fill_type="solid")
    header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    data_font = Font(name="Segoe UI", size=10, color="1F2937")
    title_font = Font(name="Segoe UI", size=14, bold=True, color=forest_green)
    bold_font = Font(name="Segoe UI", size=10, bold=True, color="111827")
    
    thin_border = Border(
        left=Side(style='thin', color=border_gray),
        right=Side(style='thin', color=border_gray),
        top=Side(style='thin', color=border_gray),
        bottom=Side(style='thin', color=border_gray)
    )

    # ── SHEET 1: EXECUTIVE OVERVIEW ─────────────────────────────────
    ws_kpi = wb.active
    ws_kpi.title = "Executive Summary"
    ws_kpi.views.sheetView[0].showGridLines = True

    ws_kpi["A1"] = "🌾 Agro AI — Farmers & Agricultural Registry"
    ws_kpi["A1"].font = title_font
    ws_kpi["A2"] = f"Report Generated: {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
    ws_kpi["A2"].font = Font(name="Segoe UI", size=9, italic=True, color="6B7280")

    kpi_headers = ["Platform Metric", "Value", "Description"]
    ws_kpi.append([])
    ws_kpi.append(kpi_headers)
    for col_idx in range(1, 4):
        cell = ws_kpi.cell(row=4, column=col_idx)
        cell.fill = PatternFill(start_color=sage_green, end_color=sage_green, fill_type="solid")
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    total_farmers = len(data)
    active_farmers = sum(1 for d in data if d["is_active"] == "Active")
    verified_farmers = sum(1 for d in data if d["is_verified"] == "Verified")
    total_acreage = sum(d["total_acres"] for d in data)
    active_subscriptions = sum(1 for d in data if d["subscription_status"].lower() == "active")
    total_diagnoses = sum(d["diagnoses_count"] for d in data)

    kpis = [
        ("Total Registered Farmers", total_farmers, "Total farmer accounts in Agro AI database"),
        ("Active Accounts", active_farmers, "Farmers currently in good active standing"),
        ("Verified Accounts", verified_farmers, "Farmers with verified mobile or email"),
        ("Total Agricultural Acreage", f"{total_acreage:.2f} Acres", "Total farmland area registered across all profiles"),
        ("Active Premium Subscriptions", active_subscriptions, "Farmers on active paid plans"),
        ("AI Crop Disease Diagnoses", total_diagnoses, "Leaf disease scans executed by farmers")
    ]

    for metric, val, desc in kpis:
        ws_kpi.append([metric, val, desc])
        curr_row = ws_kpi.max_row
        ws_kpi.cell(row=curr_row, column=1).font = bold_font
        ws_kpi.cell(row=curr_row, column=2).font = bold_font
        ws_kpi.cell(row=curr_row, column=2).alignment = Alignment(horizontal="right")
        ws_kpi.cell(row=curr_row, column=3).font = data_font
        for c in range(1, 4):
            ws_kpi.cell(row=curr_row, column=c).border = thin_border

    ws_kpi.column_dimensions['A'].width = 30
    ws_kpi.column_dimensions['B'].width = 18
    ws_kpi.column_dimensions['C'].width = 50

    # ── SHEET 2: FARMERS REGISTRY ───────────────────────────────────
    ws = wb.create_sheet(title="Farmers Registry")
    ws.views.sheetView[0].showGridLines = True

    columns = [
        ("Farmer ID", "id"),
        ("Full Name", "full_name"),
        ("Phone Number", "phone"),
        ("Email Address", "email"),
        ("Preferred Language", "preferred_language"),
        ("Account Status", "is_active"),
        ("Verification Status", "is_verified"),
        ("Registration Date", "registered_at"),
        ("State", "state"),
        ("District", "district"),
        ("Pincode", "pincode"),
        ("Total Acres", "total_acres"),
        ("Owned Acres", "owned_acres"),
        ("Leased Acres", "leased_acres"),
        ("Soil Type", "soil_type"),
        ("Irrigation Method", "irrigation_method"),
        ("Water Source", "water_source"),
        ("Cultivated Crops", "crops"),
        ("Current Subscription Plan", "subscription_plan"),
        ("Subscription Status", "subscription_status"),
        ("Valid Until", "subscription_valid_until"),
        ("AI Diagnoses Scans", "diagnoses_count"),
        ("Payment Orders Count", "orders_count"),
    ]

    # Write header
    headers = [col[0] for col in columns]
    ws.append(headers)
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border
    ws.row_dimensions[1].height = 28

    # Write data rows
    for row_data in data:
        row_values = [row_data.get(col[1]) for col in columns]
        ws.append(row_values)
        row_idx = ws.max_row
        ws.row_dimensions[row_idx].height = 20

        # Alternate row fill
        is_even = (row_idx % 2 == 0)
        row_fill = PatternFill(start_color="F9FBF9" if is_even else "FFFFFF", fill_type="solid")

        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.font = data_font
            cell.border = thin_border
            cell.fill = row_fill
            # Center alignments for status/date
            if col_idx in (5, 6, 7, 8, 11, 20, 21):
                cell.alignment = Alignment(horizontal="center")
            elif col_idx in (12, 13, 14, 22, 23):
                cell.alignment = Alignment(horizontal="right")

    # Auto-adjust column widths
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            val_str = str(cell.value or '')
            max_len = max(max_len, len(val_str))
        ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 45)

    ws.freeze_panes = "A2"

    buf = io.BytesIO()
    wb.save(buf)
    excel_bytes = buf.getvalue()
    buf.close()

    # Save physical copy to disk
    try:
        os.makedirs(EXPORT_DIR, exist_ok=True)
        file_path = os.path.join(EXPORT_DIR, "farmers_registry.xlsx")
        with open(file_path, "wb") as f:
            f.write(excel_bytes)
    except Exception as exc:
        print(f"Warning: could not save local file to disk: {exc}")

    return excel_bytes


def generate_farmers_csv_bytes(data: List[Dict[str, Any]]) -> bytes:
    """Generates standard RFC 4180 CSV with UTF-8 BOM for instant Excel opening."""
    output = io.StringIO()
    # UTF-8 BOM so Microsoft Excel opens accented and regional characters cleanly
    output.write('\ufeff')

    if not data:
        return output.getvalue().encode('utf-8')

    fieldnames = list(data[0].keys())
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in data:
        writer.writerow(row)

    csv_str = output.getvalue()
    output.close()
    csv_bytes = csv_str.encode('utf-8')

    try:
        os.makedirs(EXPORT_DIR, exist_ok=True)
        csv_path = os.path.join(EXPORT_DIR, "farmers_registry.csv")
        with open(csv_path, "wb") as f:
            f.write(csv_bytes)
    except Exception as exc:
        print(f"Warning: could not save local CSV to disk: {exc}")

    return csv_bytes

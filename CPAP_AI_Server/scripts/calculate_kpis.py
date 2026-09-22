"""
SleepCare CPAP AI Supervisor Server - Comprehensive KPI Computation Engine
===========================================================================
Calculates cohort-wide clinical adherence, risk stratification, anomaly alarms,
wearable biomarker telemetry, and video intervention coaching KPIs across all 41,117 patients.
Outputs results to CPAP_AI_SERVER_KPIS.txt and cpap_kpis_summary.json.
"""

import os
import sys
import json
import time
import numpy as np
import pandas as pd

# Add parent directory to sys.path to allow imports from core
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.interceptor import find_artifact_file, _original_read_csv

def compute_and_save_kpis():
    start_t = time.time()
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    print("[KPI ENGINE] Loading primary pipeline datasets...")
    pap_path = find_artifact_file("patient_action_plan.csv")
    feats_path = find_artifact_file("features_merged.csv")
    l0_path = find_artifact_file("layer0_results.csv")
    l3_path = find_artifact_file("layer3_results.csv")
    l6_path = find_artifact_file("layer6_events.csv")

    pap = _original_read_csv(pap_path)
    feats = _original_read_csv(feats_path)
    l0 = _original_read_csv(l0_path)
    l3 = _original_read_csv(l3_path)
    l6 = _original_read_csv(l6_path) if os.path.exists(l6_path) else None

    total_patients = len(pap)

    # -------------------------------------------------------------
    # 1. Cohort Volume & Multimodal Device Coverage KPIs
    # -------------------------------------------------------------
    ww_count = int((~feats['ww_absent'].astype(bool)).sum()) if 'ww_absent' in feats else 0
    bpm_count = int((~feats['bpm_absent'].astype(bool)).sum()) if 'bpm_absent' in feats else 0
    masimo_count = int((~feats['masimo_absent'].astype(bool)).sum()) if 'masimo_absent' in feats else 0
    hexo_count = int((~feats['hexoskin_absent'].astype(bool)).sum()) if 'hexoskin_absent' in feats else 0
    somno_count = int((~feats['somnoart_absent'].astype(bool)).sum()) if 'somnoart_absent' in feats else 0
    multimodal_patients = int((feats['n_devices'] > 0).sum()) if 'n_devices' in feats else 0

    # -------------------------------------------------------------
    # 2. Therapy Adherence & Clinical Efficacy KPIs
    # -------------------------------------------------------------
    use_series = feats['use_mean_7d'].dropna()
    mean_use_7d = float(use_series.mean())
    median_use_7d = float(use_series.median())
    std_use_7d = float(use_series.std())
    pct_compliant_4h = float((feats['use_mean_7d'] >= 4.0).mean() * 100.0)
    pct_subtherapeutic = float(((feats['use_mean_7d'] < 4.0) & (feats['use_mean_7d'] > 0.0)).mean() * 100.0)
    pct_zero_use = float((feats['use_mean_7d'] == 0.0).mean() * 100.0)

    ahi_series = feats['ahi_mean_7d'].dropna()
    mean_ahi = float(ahi_series.mean())
    median_ahi = float(ahi_series.median())
    pct_ahi_normal = float((feats['ahi_mean_7d'] < 5.0).mean() * 100.0)
    pct_ahi_mild = float(((feats['ahi_mean_7d'] >= 5.0) & (feats['ahi_mean_7d'] < 15.0)).mean() * 100.0)
    pct_ahi_moderate = float(((feats['ahi_mean_7d'] >= 15.0) & (feats['ahi_mean_7d'] < 30.0)).mean() * 100.0)
    pct_ahi_severe = float((feats['ahi_mean_7d'] >= 30.0).mean() * 100.0)

    leak_series = feats['leaks95_mean_7d'].dropna()
    mean_leak = float(leak_series.mean())
    pct_leak_elevated = float((feats['leaks95_mean_7d'] >= 24.0).mean() * 100.0)
    pct_leak_critical = float((feats['leaks95_mean_7d'] >= 40.0).mean() * 100.0)
    mean_pressure = float(feats['pressure_mean'].dropna().mean()) if 'pressure_mean' in feats else 0.0

    # -------------------------------------------------------------
    # 3. Surveillance Alarms & Anomaly Detection KPIs
    # -------------------------------------------------------------
    total_alarms = int(l0['any_alarm'].sum()) if 'any_alarm' in l0 else 0
    pct_alarm_rate = float((l0['any_alarm'] == 1).mean() * 100.0) if 'any_alarm' in l0 else 0.0
    cusum_use_alarms = int(l0['cusum_use_alarm'].sum()) if 'cusum_use_alarm' in l0 else 0
    cusum_ahi_alarms = int(l0['cusum_ahi_alarm'].sum()) if 'cusum_ahi_alarm' in l0 else 0
    ewma_use_alarms = int(l0['ewma_use_alarm'].sum()) if 'ewma_use_alarm' in l0 else 0

    # -------------------------------------------------------------
    # 4. AI Risk Stratification & Survival / Dropout KPIs
    # -------------------------------------------------------------
    risk_counts = pap['risk_level'].str.lower().value_counts(dropna=False).to_dict()
    low_risk_count = risk_counts.get('low', 0)
    med_risk_count = risk_counts.get('medium', 0)
    high_risk_count = risk_counts.get('high', 0)

    mean_z_risk = float(pap['z_risk'].dropna().mean())
    median_z_risk = float(pap['z_risk'].dropna().median())
    p95_z_risk = float(np.percentile(pap['z_risk'].dropna(), 95))

    dropout_mech_counts = pap['dropout_mechanism'].value_counts(dropna=False).to_dict()

    # -------------------------------------------------------------
    # 5. Wearable Biomarker Anomaly KPIs
    # -------------------------------------------------------------
    afib_count = int((feats['afib_detected'] == True).sum()) if 'afib_detected' in feats else 0
    hypoxia_severe_count = int((feats['spo2_7d'] < 88.0).sum()) if 'spo2_7d' in feats else 0
    hypoxia_mild_count = int(((feats['spo2_7d'] >= 88.0) & (feats['spo2_7d'] < 90.0)).sum()) if 'spo2_7d' in feats else 0
    hypertension_count = int((feats['systolic_bp_7d'] >= 140.0).sum()) if 'systolic_bp_7d' in feats else 0
    sleep_eff_poor_count = int((feats['sleep_efficiency_7d'] < 75.0).sum()) if 'sleep_efficiency_7d' in feats else 0

    # -------------------------------------------------------------
    # 6. Clinical Interventions & Multi-Scenario Video KPIs
    # -------------------------------------------------------------
    interv_counts = pap['intervention_rec'].value_counts(dropna=False).to_dict()
    surveys_to_send_count = int((pap['surveys_to_send'] != 'none').sum())
    pct_surveys = float(surveys_to_send_count / total_patients * 100.0)

    video_rec_count = int((pap['intervention_rec'].str.lower() == 'video').sum())
    urgent_flags_count = int((pap['event_detected'] == True).sum()) if 'event_detected' in pap else 0
    non_responders_count = int((pap['non_responder'] == True).sum()) if 'non_responder' in pap else 0

    top_videos_list = pap['video_title'].value_counts(dropna=False).head(5).to_dict()

    elapsed_s = round(time.time() - start_t, 2)

    # -------------------------------------------------------------
    # 7. Generate Formatted Text Report
    # -------------------------------------------------------------
    report_lines = [
        "=" * 85,
        "          SLEEPCARE CPAP AI SUPERVISOR SERVER - CLINICAL & OPERATIONAL KPIS",
        "=" * 85,
        f" Report Generated : {timestamp}",
        f" Total Cohort Size: {total_patients:,} active monitored patients",
        f" Computation Time : {elapsed_s:.2f} seconds",
        "=" * 85,
        "",
        "-------------------------------------------------------------------------------------",
        " 1. THERAPY ADHERENCE & CLINICAL EFFICACY KPIS",
        "-------------------------------------------------------------------------------------",
        f"  * 7-Day Mean Usage Duration      : {mean_use_7d:.2f} hours/night (Median: {median_use_7d:.2f}h, Std: {std_use_7d:.2f}h)",
        f"  * CMS Therapy Compliance (>= 4h) : {pct_compliant_4h:6.2f}% ({(pct_compliant_4h*total_patients/100):,.0f} patients compliant)",
        f"  * Sub-therapeutic Usage (< 4h)   : {pct_subtherapeutic:6.2f}% ({(pct_subtherapeutic*total_patients/100):,.0f} patients at risk)",
        f"  * Zero Adherence (Dropout/Aversion): {pct_zero_use:6.2f}% ({(pct_zero_use*total_patients/100):,.0f} patients with 0h)",
        "",
        f"  * 7-Day Mean Residual AHI        : {mean_ahi:.2f} events/hr (Median: {median_ahi:.2f} /hr)",
        f"    - Controlled Normal (< 5/hr)   : {pct_ahi_normal:6.2f}% ({(pct_ahi_normal*total_patients/100):,.0f} patients)",
        f"    - Mild Apnea (5 - 14.9/hr)     : {pct_ahi_mild:6.2f}% ({(pct_ahi_mild*total_patients/100):,.0f} patients)",
        f"    - Moderate Apnea (15 - 29.9/hr): {pct_ahi_moderate:6.2f}% ({(pct_ahi_moderate*total_patients/100):,.0f} patients)",
        f"    - Severe Apnea (>= 30/hr)      : {pct_ahi_severe:6.2f}% ({(pct_ahi_severe*total_patients/100):,.0f} patients)",
        "",
        f"  * 95th Percentile Mask Leak      : {mean_leak:.2f} L/min (Mean)",
        f"    - Elevated Leak (>= 24 L/min)  : {pct_leak_elevated:6.2f}% ({(pct_leak_elevated*total_patients/100):,.0f} patients flagged)",
        f"    - Critical Leak (>= 40 L/min)  : {pct_leak_critical:6.2f}% ({(pct_leak_critical*total_patients/100):,.0f} patients urgent)",
        f"  * Mean Delivered Pressure        : {mean_pressure:.2f} cmH2O",
        "",
        "-------------------------------------------------------------------------------------",
        " 2. REAL-TIME TELEMETRY ALARMS & STATISTICAL SURVEILLANCE KPIS (LAYER 0)",
        "-------------------------------------------------------------------------------------",
        f"  * Total Active Alarms (Any Alarm): {total_alarms:8,d} ({pct_alarm_rate:.2f}% of active cohort)",
        f"  * CUSUM Usage Degradation Alarms : {cusum_use_alarms:8,d} (Significant drop in nightly wear time)",
        f"  * CUSUM AHI Spike Alarms         : {cusum_ahi_alarms:8,d} (Sudden breakthrough residual events)",
        f"  * EWMA Usage Trend Alarms        : {ewma_use_alarms:8,d} (Gradual multi-day adherence decline)",
        "",
        "-------------------------------------------------------------------------------------",
        " 3. AI RISK STRATIFICATION & SURVIVAL / DROPOUT KPIS (LAYERS 1–3)",
        "-------------------------------------------------------------------------------------",
        f"  * Mean z_risk Score              : {mean_z_risk:.4f} (Median: {median_z_risk:.4f}, 95th percentile: {p95_z_risk:.4f})",
        f"  * Cohort Risk Tier Breakdown     :",
        f"    - Low Risk Tier                : {low_risk_count:8,d} ({low_risk_count/total_patients*100:6.2f}%)",
        f"    - Medium Risk Tier             : {med_risk_count:8,d} ({med_risk_count/total_patients*100:6.2f}%)",
        f"    - High Risk Tier               : {high_risk_count:8,d} ({high_risk_count/total_patients*100:6.2f}%)",
        "",
        f"  * Top Identified Dropout Mechanisms (Root Causes):",
    ]

    for mech, cnt in list(dropout_mech_counts.items())[:6]:
        report_lines.append(f"    - {mech:<32}: {cnt:8,d} ({cnt/total_patients*100:6.2f}%)")

    report_lines.extend([
        "",
        "-------------------------------------------------------------------------------------",
        " 4. MULTIMODAL WEARABLE BIOMARKER SURVEILLANCE KPIS (LAYER 5)",
        "-------------------------------------------------------------------------------------",
        f"  * Multimodal Device Monitored Cohort: {multimodal_patients:8,d} patients with active wearable telemetry",
        f"    - Withings ScanWatch Stream       : {ww_count:8,d} active feeds",
        f"    - Withings BPM Core Blood Pressure: {bpm_count:8,d} active feeds",
        f"    - Masimo Rad-G Pulse Oximetry     : {masimo_count:8,d} active feeds",
        f"    - Hexoskin Smart Vest Stream      : {hexo_count:8,d} active feeds",
        f"    - SomnoArt Hypnogram EEG Stream   : {somno_count:8,d} active feeds",
        "",
        f"  * Flagged Physiological Anomalies   :",
        f"    - Nocturnal Cardiac Afib Detected : {afib_count:8,d} patients flagged",
        f"    - Severe Hypoxia (SpO2 < 88%)     : {hypoxia_severe_count:8,d} patients urgent",
        f"    - Morning Hypertension (>= 140 mmHg): {hypertension_count:8,d} patients flagged",
        f"    - Poor Sleep Efficiency (< 75%)   : {sleep_eff_poor_count:8,d} patients flagged",
        "",
        "-------------------------------------------------------------------------------------",
        " 5. CLINICAL INTERVENTION & COACHING VIDEO KPIS (LAYERS 4–6)",
        "-------------------------------------------------------------------------------------",
        f"  * Recommended Action Plan Distribution:",
    ])

    for act, cnt in interv_counts.items():
        report_lines.append(f"    - {act:<32}: {cnt:8,d} ({cnt/total_patients*100:6.2f}%)")

    report_lines.extend([
        "",
        f"  * Medical Survey Questionnaires Dispatched: {surveys_to_send_count:8,d} ({pct_surveys:.2f}% of cohort)",
        f"  * Acute Event Urgent Review Flags         : {urgent_flags_count:8,d} ({urgent_flags_count/total_patients*100:.2f}%)",
        f"  * Identified Non-Responder Patients       : {non_responders_count:8,d} ({non_responders_count/total_patients*100:.2f}%)",
        "",
        f"  * Top 5 Prescribed Clinical Coaching Videos (Scenario 1 & 2):",
    ])

    for vid, cnt in top_videos_list.items():
        report_lines.append(f"    - {str(vid):<45}: {cnt:8,d} ({cnt/total_patients*100:6.2f}%)")

    report_lines.extend([
        "",
        "=" * 85,
        " [END OF REPORT - SLEEPCARE CPAP AI SUPERVISOR SERVER]",
        "=" * 85,
    ])

    # Ensure reports directory exists
    os.makedirs("reports", exist_ok=True)

    report_text = "\n".join(report_lines)

    # Write to text file
    txt_filename = os.path.join("reports", "CPAP_AI_SERVER_KPIS.txt")
    with open(txt_filename, "w", encoding="utf-8") as f:
        f.write(report_text)
    print(f"[KPI ENGINE] Formatted text report written to: {txt_filename}")

    # Write machine-readable JSON
    json_filename = os.path.join("reports", "cpap_kpis_summary.json")
    kpi_dict = {
        "metadata": {
            "timestamp": timestamp,
            "cohort_total": total_patients,
            "computation_time_s": elapsed_s
        },
        "adherence_efficacy": {
            "mean_use_7d": round(mean_use_7d, 2),
            "median_use_7d": round(median_use_7d, 2),
            "pct_compliant_4h": round(pct_compliant_4h, 2),
            "pct_subtherapeutic": round(pct_subtherapeutic, 2),
            "pct_zero_use": round(pct_zero_use, 2),
            "mean_residual_ahi": round(mean_ahi, 2),
            "pct_ahi_controlled": round(pct_ahi_normal, 2),
            "pct_ahi_severe": round(pct_ahi_severe, 2),
            "mean_mask_leak": round(mean_leak, 2),
            "pct_leak_elevated": round(pct_leak_elevated, 2),
            "mean_delivered_pressure": round(mean_pressure, 2)
        },
        "alarms_surveillance": {
            "total_active_alarms": total_alarms,
            "alarm_rate_pct": round(pct_alarm_rate, 2),
            "cusum_use_alarms": cusum_use_alarms,
            "cusum_ahi_alarms": cusum_ahi_alarms,
            "ewma_use_alarms": ewma_use_alarms
        },
        "risk_stratification": {
            "mean_z_risk": round(mean_z_risk, 4),
            "low_risk_count": low_risk_count,
            "medium_risk_count": med_risk_count,
            "high_risk_count": high_risk_count,
            "dropout_mechanisms": dropout_mech_counts
        },
        "wearable_biomarkers": {
            "multimodal_patients": multimodal_patients,
            "afib_detected": afib_count,
            "severe_hypoxia": hypoxia_severe_count,
            "hypertension": hypertension_count,
            "poor_sleep_efficiency": sleep_eff_poor_count
        },
        "interventions_and_videos": {
            "action_plan_distribution": interv_counts,
            "surveys_dispatched": surveys_to_send_count,
            "acute_events_urgent": urgent_flags_count,
            "top_coaching_videos": top_videos_list
        }
    }
    with open(json_filename, "w", encoding="utf-8") as f:
        json.dump(kpi_dict, f, indent=2)
    print(f"[KPI ENGINE] JSON summary written to: {json_filename}")

    return report_text

if __name__ == "__main__":
    compute_and_save_kpis()

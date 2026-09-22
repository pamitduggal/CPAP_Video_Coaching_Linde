# SleepCare API Auto-Loader Site-customize
try:
    import api_data_loader
except Exception as e:
    print(f"[SITE-CUSTOMIZE WARNING] Failed to load api_data_loader: {e}")


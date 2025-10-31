# TODO: Fix drf_spectacular settings

- [x] Add 'drf_spectacular' to INSTALLED_APPS in backend/backend/settings.py
- [x] Add 'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema' to REST_FRAMEWORK in backend/backend/settings.py
- [x] Rename SpectacularAPIView to 'schema' in backend/backend/urls.py
- [x] Add SpectacularRedocView to backend/backend/urls.py

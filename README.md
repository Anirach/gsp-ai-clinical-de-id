# Clinical Text De-Identification System (Thai/English)

A proof-of-concept application for de-identifying personally identifiable information (PII/PHI) from Thai and English clinical text while preserving analytical utility.

## Features

- **Bilingual Support**: Thai (PyThaiNLP) and English (Microsoft Presidio) text processing
- **Comprehensive Detection**: Names, IDs, addresses, dates, phone numbers, and more
- **Policy-Driven Transformations**: Redact, mask, generalize, date-shift, pseudonymize
- **Deterministic Pseudonyms**: HMAC-based pseudonymization with key derivation
- **Complete Audit Trail**: Full traceability of all detection and transformation operations
- **Human Review Interface**: Quality assurance and feedback collection
- **Regulatory Compliance**: PDPA, HIPAA Safe Harbor, GDPR alignment

## Architecture

```
├── backend/
│   ├── src/
│   │   ├── api/           # REST API endpoints
│   │   ├── services/      # Core de-identification services
│   │   ├── models/        # Data models and schemas
│   │   ├── utils/         # Utility functions
│   │   └── security/      # Security and access control
├── frontend/              # React-based reviewer UI
├── config/               # Configuration files
├── tests/                # Test suites
├── data/                 # Sample data and dictionaries
└── docs/                 # Documentation
```

## Quick Start

1. Install dependencies:
```bash
pip install -r requirements.txt
npm install --prefix frontend
```

2. Configure environment:
```bash
cp .env.example .env
# Edit .env with your settings
```

3. Start services:
```bash
# Backend API
python backend/src/main.py

# Frontend UI (in separate terminal)
cd frontend && npm start
```

## Security Features

- TLS encryption for all communications
- Role-based access control (RBAC)
- Key management with HKDF/HMAC
- Immutable audit logs
- Configurable data retention

## Compliance

This system is designed to support:
- **PDPA (Thailand)**: Personal data protection requirements
- **HIPAA Safe Harbor**: 18 identifier categories
- **GDPR**: Data protection and privacy by design

## License

Proprietary - Clinical Research Use Only
# WorkDataHub Secrets Management Policy

## Overview

This document establishes comprehensive guidelines for managing secrets, credentials, and sensitive configuration data within WorkDataHub. These policies ensure security, compliance, and operational consistency across all environments.

## 1. Guiding Principles

### 1.1 Security First
- **Never commit secrets** to version control
- **Rotate credentials regularly** (minimum quarterly for production)
- **Apply least privilege** - grant only necessary access
- **Use strong authentication** - multi-factor where possible

### 1.2 Environment Separation
- **Separate configurations** for dev, staging, production
- **Isolated credentials** - no credential sharing across environments  
- **Environment-specific access** controls

### 1.3 Transparency & Auditability
- **Document all secrets** and their purpose
- **Log access patterns** (without exposing values)
- **Regular security audits** of credential usage

## 2. Secrets Classification

### 2.1 High Sensitivity
- Database passwords and connection strings
- API keys for external services
- Encryption keys and certificates
- Authentication tokens

### 2.2 Medium Sensitivity  
- Service endpoints and URLs
- Non-production credentials
- Configuration parameters affecting security

### 2.3 Low Sensitivity
- Feature flags and operational settings
- Non-sensitive application configuration
- Development-only parameters

## 3. Storage & Management Patterns

### 3.1 Local Development

**✅ RECOMMENDED:**
```bash
# Use .env files for local development
cp .env.example .env
# Edit .env with your local values
# .env is automatically git-ignored
```

**❌ PROHIBITED:**
- Hardcoding secrets in source code
- Committing .env files to version control
- Sharing credentials via chat/email
- Using production credentials locally

### 3.2 Environment Variables

**Standard Naming Convention:**
- Use `WDH_` prefix for all WorkDataHub variables
- Use `WDH_DATABASE__` for nested database configuration
- Follow SCREAMING_SNAKE_CASE for environment variable names

**Examples:**
```bash
# Application settings
WDH_APP_NAME=WorkDataHub
WDH_DEBUG=false
WDH_LOG_LEVEL=INFO

# Database configuration (nested with double underscore)
WDH_DATABASE__HOST=localhost
WDH_DATABASE__PORT=5432
WDH_DATABASE__USER=wdh_user
WDH_DATABASE__PASSWORD=secure_password_here
WDH_DATABASE__DB=wdh

# Optional URI override
WDH_DATABASE__URI=postgresql://user:pass@host:port/db
```

### 3.3 Production Deployment

**✅ RECOMMENDED:**
- Use container orchestration secrets (Docker Swarm, Kubernetes)
- Leverage cloud provider secret management (AWS Secrets Manager, Azure Key Vault)
- Implement automated credential rotation
- Use service meshes for internal service authentication

**❌ PROHIBITED:**
- Plain text files on production servers
- Environment variables visible in process lists
- Shared service accounts across environments

## 4. Loading & Configuration

### 4.1 Pydantic Settings Integration

WorkDataHub uses `pydantic-settings` for configuration management:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    model_config = ConfigDict(
        env_prefix="WDH_",           # All variables prefixed with WDH_
        env_file=".env",             # Load from .env file if present
        env_file_encoding="utf-8",   # UTF-8 encoding
        case_sensitive=False,        # Case-insensitive variable matching
    )
```

### 4.2 Loading Priority (Highest to Lowest)
1. Environment variables
2. `.env` file variables  
3. Default values in Settings class

### 4.3 Validation & Type Safety
- All configuration uses Pydantic models with type hints
- Validation occurs at application startup
- Invalid configurations cause immediate startup failure

## 5. CI/CD Integration

### 5.1 GitHub Actions Secrets

**Setup Process:**
1. Navigate to repository Settings → Secrets and variables → Actions
2. Create secrets with `WDH_` prefix matching environment variables
3. Reference in workflows using `${{ secrets.WDH_DATABASE_PASSWORD }}`

**Example Workflow:**
```yaml
env:
  WDH_DATABASE__HOST: ${{ secrets.WDH_DATABASE_HOST }}
  WDH_DATABASE__PASSWORD: ${{ secrets.WDH_DATABASE_PASSWORD }}
```

### 5.2 Security Scanning
- **Gitleaks** integration prevents credential commits
- **Dependency scanning** for vulnerable packages  
- **SAST scanning** for hardcoded secrets

## 6. Code Review & Compliance

### 6.1 Mandatory Review Items
- [ ] No hardcoded credentials in source code
- [ ] Environment variables follow WDH_ naming convention
- [ ] .env.example updated with new variables
- [ ] Sensitive values not logged or exposed in error messages
- [ ] Database queries use parameterized statements

### 6.2 Pull Request Checklist
```markdown
## Security Review Checklist
- [ ] No secrets in source code or git history
- [ ] Environment variables properly prefixed (WDH_)
- [ ] .env.example reflects all required variables
- [ ] Error handling doesn't expose sensitive data
- [ ] Database operations use proper escaping
```

## 7. Incident Response

### 7.1 Credential Compromise Response

**IMMEDIATE (Within 1 Hour):**
1. **Revoke compromised credentials** immediately
2. **Generate new credentials** with different values
3. **Update all affected systems** with new credentials
4. **Document incident** with timeline and impact

**SHORT-TERM (Within 24 Hours):**
1. **Audit access logs** for unauthorized usage
2. **Review affected data** for potential exposure
3. **Notify stakeholders** as required by policy
4. **Implement additional monitoring** for the affected service

**LONG-TERM (Within 1 Week):**
1. **Root cause analysis** - how was credential exposed?
2. **Process improvements** to prevent recurrence
3. **Security training** for team members if needed
4. **Updated policies** based on lessons learned

### 7.2 Detection Methods
- **Automated scanning** with tools like gitleaks
- **Log monitoring** for unusual access patterns
- **Regular credential audits** and rotation
- **External security reports** or notifications

## 8. Environment-Specific Guidelines

### 8.1 Development Environment
```bash
# Safe defaults for local development
WDH_DATABASE__HOST=localhost
WDH_DATABASE__PORT=5432
WDH_DATABASE__USER=wdh_dev
WDH_DATABASE__PASSWORD=dev_password_123
WDH_DATABASE__DB=wdh_dev
WDH_DEBUG=true
WDH_LOG_LEVEL=DEBUG
```

### 8.2 Production Environment
```bash
# Production should use secure values
WDH_DATABASE__PASSWORD=<strong-generated-password>
WDH_DEBUG=false  
WDH_LOG_LEVEL=INFO
# Use WDH_DATABASE__URI for managed database services
WDH_DATABASE__URI=<managed-database-connection-string>
```

## 9. Tools & Resources

### 9.1 Recommended Tools
- **Password Managers**: 1Password, Bitwarden for team credential sharing
- **Secret Scanners**: gitleaks, truffleHog, GitHub secret scanning
- **Credential Rotation**: Cloud provider native tools (AWS, Azure, GCP)
- **Monitoring**: Application logs, audit trails, security information and event management (SIEM)

### 9.2 Reference Documentation
- [.env.example](../.env.example) - Template with all WDH_* variables
- [pydantic-settings Documentation](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [GitHub Actions Secrets](https://docs.github.com/en/actions/security-guides/encrypted-secrets)

## 10. Compliance & Auditing

### 10.1 Regular Audits (Monthly)
- [ ] Review all active credentials and their last rotation date
- [ ] Verify .env.example is up-to-date with current variables
- [ ] Check for any hardcoded secrets in recent commits
- [ ] Validate environment variable naming conventions

### 10.2 Security Metrics
- Time to credential rotation (target: < 90 days)
- Number of credential-related incidents (target: 0)
- Code review coverage for security checklist items (target: 100%)
- Secret scanning coverage (target: all repositories)

---

## Revision History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2025-09-07 | Initial comprehensive secrets policy | CI Implementation |

---

**Remember: When in doubt, treat data as sensitive and apply the highest security standards. It's better to be overly cautious than to experience a security incident.**